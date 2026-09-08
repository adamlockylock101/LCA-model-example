"""Tests for the LCA model.

Two things are being defended here:

1. The arithmetic. Totals must be reconstructable by hand from the printed
   stage breakdown, and the biogenic carbon credit must always be mirrored by
   the end-of-life release of that same carbon.

2. The integrity of the confidence system. A placeholder anywhere in a chain
   must reach the output as a visible flag. This is the property the whole tool
   exists to guarantee, so it is tested harder than the maths.

Numbers tagged "derived" in inputs.toml are re-derived here from molar masses.
If someone edits one of those values by hand without changing the chemistry,
these tests fail -- which is the point.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lca_film.calculate import (  # noqa: E402
    biogenic_carbon_fraction,
    evaluate,
    evaluate_all,
    raw_material_item,
)
from lca_film.boundary import is_comparable  # noqa: E402
from lca_film.chart import _axis_peak, render_svg  # noqa: E402
from lca_film.config import DEFAULT_INPUTS, list_scenarios, load_study  # noqa: E402
from lca_film.confidence import Confidence, weakest  # noqa: E402
from lca_film.report import (  # noqa: E402
    boundary_report,
    full_report,
    sensitivity,
    trace,
)
from lca_film.__main__ import main, parse_set  # noqa: E402

# Molar masses, independent of the config file, so the tests are a real check
# and not a restatement of the inputs.
M_C, M_H, M_O, M_NA = 12.011, 1.008, 15.999, 22.990
M_CO2 = M_C + 2 * M_O
CO2_PER_C = M_CO2 / M_C


def carbon_fraction(c: int, h: int, o: int, na: int = 0) -> float:
    mw = c * M_C + h * M_H + o * M_O + na * M_NA
    return c * M_C / mw


class TestConfidence(unittest.TestCase):
    def test_weakest_wins(self):
        self.assertIs(
            weakest([Confidence.LITERATURE, Confidence.ESTIMATE, Confidence.PLACEHOLDER]),
            Confidence.PLACEHOLDER,
        )
        self.assertIs(
            weakest([Confidence.LITERATURE, Confidence.DERIVED]), Confidence.DERIVED
        )

    def test_empty_defaults_to_derived(self):
        self.assertIs(weakest([]), Confidence.DERIVED)

    def test_every_tag_prints_a_marker(self):
        for level in Confidence:
            self.assertTrue(level.marker.strip())
            self.assertTrue(level.label.strip())

    def test_unknown_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            Confidence.parse("probably_fine")


class TestValidation(unittest.TestCase):
    """The loader must refuse inputs that would quietly weaken the model."""

    BASE = """
[constants]
m_c = 12.011
m_co2 = 44.009
m_ch4 = 16.043
gwp100_biogenic_methane = 27.0

[[materials]]
id = "x"
name = "X"
carbon_mass_fraction = 0.5
biogenic_carbon_mass_fraction = 0.0
[[materials.stages]]
label = "Raw material"
value = 1.0
confidence = "{raw_conf}"
{raw_extra}
[[materials.eol_routes]]
id = "landfill"
label = "Landfill"
value = 0.1
confidence = "estimate"
"""

    def _load(self, **kwargs):
        text = self.BASE.format(
            raw_conf=kwargs.get("raw_conf", "estimate"),
            raw_extra=kwargs.get("raw_extra", ""),
        )
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write(text)
            path = fh.name
        return load_study(path)

    def test_literature_without_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires a 'source'"):
            self._load(raw_conf="literature")

    def test_derived_without_derivation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires a 'derivation'"):
            self._load(raw_conf="derived")

    def test_value_outside_its_own_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "below low"):
            self._load(raw_extra="low = 5.0\nhigh = 9.0")

    def test_valid_input_loads(self):
        study = self._load(raw_conf="literature", raw_extra='source = "somewhere"')
        self.assertEqual(study.materials[0].id, "x")

    def test_composition_must_sum_to_one(self):
        text = self.BASE.format(raw_conf="estimate", raw_extra="") + """
[[materials]]
id = "y"
name = "Y"
[[materials.composition]]
component = "A"
mass_fraction = 0.5
frac_confidence = "estimate"
carbon_mass_fraction = 0.4
biogenic = true
value = 1.0
confidence = "estimate"
[[materials.composition]]
component = "B"
mass_fraction = 0.2
frac_confidence = "estimate"
carbon_mass_fraction = 0.4
biogenic = true
value = 1.0
confidence = "estimate"
[[materials.eol_routes]]
id = "compost"
label = "Compost"
value = 0.1
confidence = "estimate"
"""
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write(text)
            path = fh.name
        with self.assertRaisesRegex(ValueError, "sum to 0.7000"):
            load_study(path)


class TestStudy(unittest.TestCase):
    def setUp(self):
        self.study = load_study()
        self.results = evaluate_all(self.study)

    def test_three_materials_present(self):
        self.assertEqual(
            {m.id for m in self.study.materials}, {"ldpe", "pva", "biofilm"}
        )

    def test_every_material_has_end_of_life_routes(self):
        for material in self.study.materials:
            self.assertGreaterEqual(len(material.eol_routes), 1, material.id)

    def test_totals_equal_the_sum_of_printed_stages(self):
        """A reader must be able to add the breakdown up by hand and match."""
        for result in self.results:
            self.assertAlmostEqual(
                result.total, sum(i.value for i in result.items), places=9, msg=result.label
            )

    def test_ranges_bracket_the_central_value(self):
        for result in self.results:
            self.assertLessEqual(result.total_low, result.total + 1e-9, result.label)
            self.assertGreaterEqual(result.total_high, result.total - 1e-9, result.label)


class TestDerivedNumbers(unittest.TestCase):
    """Re-derive the config's 'derived' values from first principles."""

    def setUp(self):
        self.study = load_study()

    def test_pva_carbon_fraction_matches_repeat_unit(self):
        # PVA repeat unit C2H4O
        expected = carbon_fraction(2, 4, 1)
        self.assertAlmostEqual(
            self.study.material("pva").carbon_mass_fraction, expected, places=3
        )

    def test_ldpe_carbon_fraction_matches_repeat_unit(self):
        # LDPE repeat unit C2H4
        expected = carbon_fraction(2, 4, 0)
        self.assertAlmostEqual(
            self.study.material("ldpe").carbon_mass_fraction, expected, places=3
        )

    def test_pva_incineration_is_full_oxidation_of_its_carbon(self):
        pva = self.study.material("pva")
        route = next(r for r in pva.eol_routes if r.id == "incineration")
        expected = carbon_fraction(2, 4, 1) * CO2_PER_C
        self.assertAlmostEqual(route.fossil.value, expected, places=2)

    def test_ldpe_incineration_upper_bound_is_full_oxidation(self):
        ldpe = self.study.material("ldpe")
        route = next(r for r in ldpe.eol_routes if r.id == "incineration")
        expected = carbon_fraction(2, 4, 0) * CO2_PER_C
        self.assertAlmostEqual(route.fossil.high, expected, places=2)

    def test_blend_component_carbon_fractions(self):
        expected = {
            # sodium alginate C6H7NaO6
            "Sodium alginate": carbon_fraction(6, 7, 6, na=1),
            # stearic acid C18H36O2
            "Stearic acid": carbon_fraction(18, 36, 2),
        }
        biofilm = self.study.material("biofilm")
        for component in biofilm.composition:
            if component.name in expected:
                self.assertAlmostEqual(
                    component.carbon_mass_fraction,
                    expected[component.name],
                    places=3,
                    msg=component.name,
                )

    def test_biogenic_credit_uses_actual_blend_carbon_not_cellulose(self):
        """The credit must come from the real blend, not a cellulose stand-in."""
        biofilm = self.study.material("biofilm")
        c_bio = biogenic_carbon_fraction(biofilm)
        expected = sum(
            c.mass_fraction.value * c.carbon_mass_fraction
            for c in biofilm.composition
            if c.biogenic
        )
        self.assertAlmostEqual(c_bio, expected, places=9)

        route = next(r for r in biofilm.eol_routes if r.id == "composting")
        result = evaluate(biofilm, route, self.study.constants)
        credit = next(i for i in result.items if i.kind == "biogenic_credit")
        self.assertAlmostEqual(credit.value, -c_bio * CO2_PER_C, places=2)

        # And it must genuinely differ from the cellulose shortcut it replaces.
        cellulose = carbon_fraction(6, 10, 5) * CO2_PER_C
        self.assertNotAlmostEqual(abs(credit.value), cellulose, places=4)

    def test_fossil_materials_take_no_biogenic_credit(self):
        for material_id in ("ldpe", "pva"):
            material = self.study.material(material_id)
            self.assertEqual(biogenic_carbon_fraction(material), 0.0, material_id)
            route = material.eol_routes[0]
            result = evaluate(material, route, self.study.constants)
            self.assertFalse(
                [i for i in result.items if i.kind == "biogenic_credit"], material_id
            )


class TestStearicAcidDerivation(unittest.TestCase):
    """The stearic acid value is interpolated, so its bracket must hold.

    Lower anchor: RSPO-certified crude palm oil, 3.41 kg CO2e/kg -- the feedstock
    before any oleochemical conversion. Upper anchor: palm-kernel-oil fatty
    alcohol, 5.27 kg CO2e/kg (Shah et al., J. Surfactants Deterg. 2016, 19,
    1333-1351), which is the same route plus two further conversion steps.
    Stearic acid sits between them by construction; if an edit moves it outside
    that bracket, the stated derivation no longer holds and this fails.
    """

    PALM_OIL_FEEDSTOCK = 3.41
    FATTY_ALCOHOL_DOWNSTREAM = 5.27

    def setUp(self):
        self.stearic = next(
            c for c in load_study().material("biofilm").composition
            if c.id == "stearic_acid"
        )

    def test_value_sits_between_its_two_published_anchors(self):
        value = self.stearic.footprint.value
        self.assertGreater(value, self.PALM_OIL_FEEDSTOCK)
        self.assertLess(value, self.FATTY_ALCOHOL_DOWNSTREAM)

    def test_value_is_the_midpoint_of_the_bracket(self):
        midpoint = (self.PALM_OIL_FEEDSTOCK + self.FATTY_ALCOHOL_DOWNSTREAM) / 2
        self.assertAlmostEqual(self.stearic.footprint.value, midpoint, delta=0.06)

    def test_range_spans_the_bracket(self):
        self.assertLessEqual(self.stearic.footprint.low_or_value, self.PALM_OIL_FEEDSTOCK)
        self.assertGreaterEqual(
            self.stearic.footprint.high_or_value, self.FATTY_ALCOHOL_DOWNSTREAM
        )

    def test_it_is_tagged_derived_not_literature(self):
        """An interpolation between two sources is not itself a sourced figure."""
        self.assertIs(self.stearic.footprint.confidence, Confidence.DERIVED)
        self.assertTrue(self.stearic.footprint.derivation)

    def test_the_unretrieved_ecoinvent_source_is_recorded_as_the_gap(self):
        self.assertIn("ecoinvent", self.stearic.footprint.note.lower())


class TestScopeVariants(unittest.TestCase):
    """A different measurement must never be usable as a bound."""

    def setUp(self):
        self.study = load_study()
        self.alginate = next(
            c for c in self.study.material("biofilm").composition if c.id == "alginate"
        )
        self.zein = next(
            c for c in self.study.material("biofilm").composition if c.id == "zein"
        )

    def test_sargassum_figure_is_a_variant_not_a_bound(self):
        variant_ids = {v.id for v in self.alginate.footprint.scope_variants}
        self.assertIn("sargassum_composite_bioplastic", variant_ids)
        self.assertGreater(self.alginate.footprint.low_or_value, 5.90)

    def test_lab_scale_zein_is_a_variant_not_a_bound(self):
        variant_ids = {v.id for v in self.zein.footprint.scope_variants}
        self.assertIn("lab_scale_solvent_extraction", variant_ids)
        self.assertLess(self.zein.footprint.high_or_value, 100.0)

    def test_the_ranges_that_were_scope_disagreement_have_collapsed(self):
        """The whole point: parametric spread is now small and meaningful."""
        self.assertLess(self.alginate.footprint.spread, 1.0)
        self.assertLess(self.zein.footprint.spread, 10.0)

    def test_every_variant_declares_what_it_measures(self):
        for component in (self.alginate, self.zein):
            for variant in component.footprint.scope_variants:
                self.assertTrue(variant.product, variant.id)
                self.assertTrue(variant.why_not_comparable, variant.id)

    def test_loader_rejects_a_non_comparable_variant_used_as_a_bound(self):
        """The guard that stops this regressing."""
        with self.assertRaisesRegex(ValueError, "cannot bound this quantity"):
            load_study(overrides=[{"path": "biofilm/component/alginate", "low": 4.00}])

    def test_loader_rejects_a_variant_that_hides_its_scope(self):
        text = DEFAULT_INPUTS.read_text(encoding="utf-8").replace(
            'why_not_comparable = "It measures a different product',
            'skip_this = "It measures a different product',
            1,
        )
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write(text)
            path = fh.name
        with self.assertRaisesRegex(ValueError, "requires 'why_not_comparable'"):
            load_study(path)

    def test_scenario_can_pull_a_variant_and_cannot_drift_from_it(self):
        study = load_study(scenario="sargassum_route")
        alginate = next(
            c for c in study.material("biofilm").composition if c.id == "alginate"
        )
        variant = next(
            v for v in self.alginate.footprint.scope_variants
            if v.id == "sargassum_composite_bioplastic"
        )
        self.assertEqual(alginate.footprint.value, variant.value)
        self.assertEqual(alginate.footprint.high_or_value, variant.high)
        self.assertIn("SCOPE VARIANT IN USE", alginate.footprint.note)

    def test_unknown_variant_id_is_rejected_with_the_available_ones(self):
        with self.assertRaisesRegex(ValueError, "available:"):
            load_study(
                overrides=[
                    {"path": "biofilm/component/zein", "variant": "does_not_exist"}
                ]
            )

    def test_variants_reach_the_report(self):
        text = full_report(self.study)
        self.assertIn("SCOPE VARIANTS", text)
        self.assertIn("NOT COMPARABLE", text)
        self.assertIn("Sargassum", text)


class TestUnquantifiedUncertainty(unittest.TestCase):
    """A narrow range must not be allowed to read as confidence."""

    def setUp(self):
        self.study = load_study()

    def test_alginate_names_its_unquantified_drivers(self):
        alginate = next(
            c for c in self.study.material("biofilm").composition if c.id == "alginate"
        )
        drivers = " ".join(alginate.footprint.unquantified).lower()
        for expected in ("yield", "allocation", "boundary", "purification"):
            self.assertIn(expected, drivers)

    def test_a_tight_range_is_accompanied_by_named_drivers(self):
        """Alginate's 0.5-wide range would otherwise imply a settled input."""
        alginate = next(
            c for c in self.study.material("biofilm").composition if c.id == "alginate"
        )
        self.assertLess(alginate.footprint.spread, 1.0)
        self.assertGreaterEqual(len(alginate.footprint.unquantified), 3)

    def test_drivers_propagate_to_the_blended_line_item(self):
        item = raw_material_item(self.study.material("biofilm"))
        self.assertTrue(item.has_unquantified)
        self.assertTrue(any("Sodium alginate" in d for d in item.unquantified))

    def test_report_prints_them_and_warns_against_misreading_the_range(self):
        text = full_report(self.study)
        self.assertIn("UNQUANTIFIED UNCERTAINTY", text)
        self.assertIn("UNQUANTIFIED:", text)  # inline, next to the number
        self.assertIn("does NOT capture", text)

    def test_sensitivity_states_what_it_does_not_rank(self):
        text = "\n".join(sensitivity(evaluate_all(self.study)))
        self.assertIn("PARAMETRIC", text)
        self.assertIn("SCOPE VARIANTS", text)


class TestBiogenicBalance(unittest.TestCase):
    """Uptake and release are computed from one carbon number, so they must tie."""

    def setUp(self):
        self.study = load_study()
        self.biofilm = self.study.material("biofilm")

    def test_full_incineration_returns_all_credited_carbon(self):
        route = next(r for r in self.biofilm.eol_routes if r.id == "incineration")
        self.assertEqual(route.biogenic_carbon_released_fraction, 1.0)
        result = evaluate(self.biofilm, route, self.study.constants)
        credit = next(i for i in result.items if i.kind == "biogenic_credit").value
        release = next(i for i in result.items if i.kind == "eol_biogenic").value
        self.assertAlmostEqual(credit + release, 0.0, places=6)

    def test_composting_methane_outweighs_the_carbon_left_in_compost(self):
        """The 5% retained carbon does NOT make composting carbon-negative.

        Only 2% of the released carbon leaves as CH4, but at GWP100 = 27 that
        small slice costs more than the sequestration credit is worth. This is
        the kind of result the model exists to make visible, so it is pinned.
        """
        route = next(r for r in self.biofilm.eol_routes if r.id == "composting")
        result = evaluate(self.biofilm, route, self.study.constants)
        credit = next(i for i in result.items if i.kind == "biogenic_credit").value
        release = next(i for i in result.items if i.kind == "eol_biogenic").value

        retained_credit = abs(credit) * (1 - route.biogenic_carbon_released_fraction)
        net_carbon = credit + release
        self.assertGreater(net_carbon, 0.0)
        self.assertGreater(net_carbon, retained_credit)

    def test_composting_without_methane_would_be_carbon_negative(self):
        """Isolate the methane: with none, the retained carbon is a real credit."""
        import dataclasses

        route = next(r for r in self.biofilm.eol_routes if r.id == "composting")
        aerobic = dataclasses.replace(route, methane_share_of_released_carbon=0.0)
        result = evaluate(self.biofilm, aerobic, self.study.constants)
        credit = next(i for i in result.items if i.kind == "biogenic_credit").value
        release = next(i for i in result.items if i.kind == "eol_biogenic").value
        self.assertAlmostEqual(
            credit + release,
            credit * (1 - aerobic.biogenic_carbon_released_fraction),
            places=6,
        )
        self.assertLess(credit + release, 0.0)

    def test_methane_makes_landfill_worse_than_composting(self):
        """Uncaptured biogenic CH4 must cost more than the same carbon as CO2."""
        compost = evaluate(
            self.biofilm,
            next(r for r in self.biofilm.eol_routes if r.id == "composting"),
            self.study.constants,
        )
        landfill = evaluate(
            self.biofilm,
            next(r for r in self.biofilm.eol_routes if r.id == "landfill"),
            self.study.constants,
        )
        self.assertGreater(landfill.total, compost.total)


class TestPlaceholderFlagging(unittest.TestCase):
    """The core promise: a placeholder can never hide inside a clean-looking result."""

    def setUp(self):
        self.study = load_study()
        self.results = evaluate_all(self.study)

    def test_biofilm_results_are_flagged(self):
        for result in self.results:
            if result.material.id == "biofilm":
                self.assertTrue(result.is_placeholder_based, result.label)
                self.assertIn("PLACEHOLDER", result.flag)

    def test_result_confidence_is_the_weakest_input(self):
        for result in self.results:
            worst = max(i.confidence.rank for i in result.items)
            self.assertEqual(result.confidence.rank, worst, result.label)

    def test_placeholder_in_a_blend_propagates_to_the_total(self):
        """One unsourced component must taint the blended raw-material figure."""
        biofilm = self.study.material("biofilm")
        item = raw_material_item(biofilm)
        self.assertTrue(item.confidence.is_placeholder)
        self.assertTrue(
            any(c.footprint.confidence.is_placeholder for c in biofilm.composition)
        )

    def test_no_placeholder_means_no_flag(self):
        for result in self.results:
            if result.material.id in ("ldpe", "pva"):
                self.assertFalse(result.is_placeholder_based, result.label)
                self.assertEqual(result.flag, "")

    def test_every_line_item_prints_with_its_tag(self):
        for result in self.results:
            for item in result.items:
                self.assertIn(f"[{item.confidence.marker}]", item.tagged)


class TestReportOutput(unittest.TestCase):
    def setUp(self):
        self.study = load_study()
        self.results = evaluate_all(self.study)
        self.text = full_report(self.study, self.results)

    def test_report_shows_the_flag_next_to_flagged_rows(self):
        self.assertIn("PLACEHOLDER-BASED", self.text)

    def test_report_lists_the_placeholder_register(self):
        self.assertIn("PLACEHOLDER REGISTER", self.text)

    def test_qualitative_flags_reach_the_report(self):
        """Impacts with no number must still be printed with the results."""
        self.assertIn("Microplastic persistence", self.text)
        self.assertIn("QUALITATIVE FLAGS", self.text)

    def test_every_material_appears(self):
        for material in self.study.materials:
            self.assertIn(material.name, self.text)

    def test_svg_renders_and_marks_placeholder_bars(self):
        svg = render_svg(self.results, "test")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.rstrip().endswith("</svg>"))
        self.assertIn("url(#ph)", svg)  # hatching applied to a flagged bar
        self.assertIn("PLACEHOLDER-BASED", svg)


class TestSwappability(unittest.TestCase):
    """Inputs must be replaceable without touching calculation code."""

    def test_replacing_the_zein_placeholder_narrows_the_result_and_lifts_the_tag(self):
        swapped = evaluate_all(
            load_study(
                overrides=[
                    {
                        "path": "biofilm/component/zein",
                        "value": 2.00,
                        "low": 1.80,
                        "high": 2.20,
                        "confidence": "literature",
                        "source": "Hypothetical sourced figure, for the swap test only.",
                    }
                ]
            )
        )
        rows = [r for r in swapped if r.material.id == "biofilm"]
        self.assertTrue(rows)
        for row in rows:
            # Zein is no longer a placeholder, but the reconstructed blend
            # ratios still are, so the flag must survive.
            self.assertTrue(row.is_placeholder_based, row.label)
            self.assertLess(row.total_high - row.total_low, 3.0, row.label)

    def test_a_scenario_file_can_be_swapped_wholesale(self):
        """--inputs must accept a different dataset with no code change."""
        text = DEFAULT_INPUTS.read_text(encoding="utf-8").replace(
            'value      = 1.80\nlow        = 1.70\nhigh       = 2.00',
            'value      = 1.20\nlow        = 1.10\nhigh       = 1.30',
            1,
        )
        self.assertNotIn("value      = 1.80", text.split("[[materials.stages]]")[1])
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write(text)
            path = fh.name
        ldpe = next(
            r for r in evaluate_all(load_study(path))
            if r.material.id == "ldpe" and r.route.id == "landfill"
        )
        self.assertAlmostEqual(ldpe.total, 1.50, places=2)


class TestBoundaryTracking(unittest.TestCase):
    """A well-sourced number on the wrong boundary is still the wrong number."""

    def setUp(self):
        self.study = load_study()

    def test_food_database_inputs_are_flagged_as_mismatched(self):
        """Alginate is the one retail-shelf figure left in the default."""
        labels = {i.input_label for i in self.study.boundary_issues()}
        self.assertEqual(labels, {"Sodium alginate raw material"})

    def test_stearic_acid_default_is_now_on_the_target_boundary(self):
        stearic = next(
            c for c in self.study.material("biofilm").composition
            if c.id == "stearic_acid"
        )
        self.assertEqual(stearic.footprint.boundary, "factory_gate")

    def test_food_database_scenario_reintroduces_both_mismatches(self):
        """The contrast scenario must still show what the wider boundary costs."""
        study = load_study(scenario="food_database_sourcing")
        labels = {i.input_label for i in study.boundary_issues()}
        self.assertEqual(
            labels, {"Sodium alginate raw material", "Stearic acid raw material"}
        )

    def test_mismatch_names_the_direction_of_the_bias(self):
        for issue in self.study.boundary_issues():
            self.assertIn("OVERSTATES", issue.direction)

    def test_polymer_eco_profiles_are_on_target_boundary(self):
        issues = {i.input_label for i in self.study.boundary_issues()}
        for material_id in ("ldpe", "pva"):
            for stage in self.study.material(material_id).stages:
                self.assertNotIn(stage.label, issues)

    def test_process_and_eol_boundaries_are_never_flagged(self):
        """Only raw-material acquisition is compared against the study target."""
        self.assertTrue(is_comparable("process", "factory_gate"))
        self.assertTrue(is_comparable("eol", "factory_gate"))
        self.assertFalse(is_comparable("retail_shelf", "factory_gate"))

    def test_boundary_report_reaches_the_full_report(self):
        text = full_report(self.study)
        self.assertIn("BOUNDARY AUDIT", text)
        self.assertIn("OVERSTATES", text)

    def test_alginate_boundary_mismatch_is_still_open(self):
        """It cannot be closed by inventing a correction, so it must stay flagged."""
        labels = {i.input_label for i in self.study.boundary_issues()}
        self.assertEqual(labels, {"Sodium alginate raw material"})
        self.assertIn("OVERSTATES", "\n".join(boundary_report(self.study)))


class TestScenarios(unittest.TestCase):
    """Swapping inputs must work from the data file, with no code change."""

    def test_scenarios_are_discoverable(self):
        names = list_scenarios()
        self.assertIn("sargassum_route", names)
        for spec in names.values():
            self.assertTrue(spec.get("label"))

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown scenario"):
            load_study(scenario="wishful_thinking")

    def test_scenario_changes_the_result(self):
        before = next(
            r for r in evaluate_all(load_study())
            if r.material.id == "biofilm" and r.route.id == "composting"
        )
        after = next(
            r for r in evaluate_all(load_study(scenario="sargassum_route"))
            if r.material.id == "biofilm" and r.route.id == "composting"
        )
        self.assertLess(after.total, before.total)
        self.assertAlmostEqual(before.total, 14.70, places=2)
        self.assertAlmostEqual(after.total, 4.33, places=2)

    def test_override_records_which_scenario_set_it(self):
        study = load_study(scenario="sargassum_route")
        alginate = next(
            c for c in study.material("biofilm").composition if c.id == "alginate"
        )
        self.assertEqual(alginate.footprint.overridden_by, "sargassum_route")

    def test_scenario_cannot_smuggle_in_an_unsourced_literature_tag(self):
        """Overrides go through the same validation as authored values."""
        with self.assertRaisesRegex(ValueError, "requires a 'source'"):
            load_study(
                overrides=[
                    {
                        "path": "biofilm/component/zein",
                        "value": 1.0,
                        "confidence": "literature",
                        "source": "",
                    }
                ]
            )

    def test_bad_override_path_is_rejected_with_a_useful_message(self):
        with self.assertRaisesRegex(ValueError, "no component 'unobtainium'"):
            load_study(overrides=[{"path": "biofilm/component/unobtainium", "value": 1.0}])
        with self.assertRaisesRegex(ValueError, "unknown path kind"):
            load_study(overrides=[{"path": "biofilm/widget/zein", "value": 1.0}])

    def test_override_replaces_a_stale_range(self):
        """A new central value must not sit inside the old bounds by accident."""
        study = load_study(overrides=[{"path": "biofilm/component/zein", "value": 900.0}])
        zein = next(c for c in study.material("biofilm").composition if c.id == "zein")
        self.assertEqual(zein.footprint.value, 900.0)
        self.assertEqual(zein.footprint.low_or_value, 900.0)
        self.assertEqual(zein.footprint.high_or_value, 900.0)

    def test_command_line_set_is_tagged_placeholder(self):
        """A number typed at a shell prompt has no source, and must say so."""
        override = parse_set("biofilm/component/zein=2.0")
        self.assertEqual(override["confidence"], "placeholder")
        study = load_study(overrides=[override])
        zein = next(c for c in study.material("biofilm").composition if c.id == "zein")
        self.assertTrue(zein.footprint.confidence.is_placeholder)
        self.assertEqual(zein.footprint.value, 2.0)

    def test_set_rejects_malformed_input(self):
        for bad in ("nonsense", "biofilm/component/zein=abc"):
            with self.assertRaises(Exception):
                parse_set(bad)

    def test_ad_hoc_override_beats_the_scenario_it_layers_on(self):
        study = load_study(
            scenario="sargassum_route",
            overrides=[parse_set("biofilm/component/alginate=9.0")],
        )
        alginate = next(
            c for c in study.material("biofilm").composition if c.id == "alginate"
        )
        self.assertEqual(alginate.footprint.value, 9.0)
        self.assertEqual(alginate.footprint.overridden_by, "--set")


class TestTrace(unittest.TestCase):
    """The audit trail is the answer to 'where did this number come from'."""

    def setUp(self):
        self.study = load_study()
        self.text = "\n".join(trace(self.study, "biofilm", "composting"))

    def test_trace_shows_the_blend_arithmetic(self):
        self.assertIn("Sodium alginate", self.text)
        self.assertIn("21.29", self.text)
        self.assertIn("12.7740", self.text)  # 0.60 x 21.29

    def test_trace_shows_the_biogenic_credit_being_applied(self):
        self.assertIn("Biogenic carbon credit", self.text)
        self.assertIn("-1.6608", self.text)
        self.assertIn("Credit applied at uptake", self.text)

    def test_trace_running_total_reaches_the_reported_total(self):
        self.assertIn("14.7000", self.text)

    def test_trace_reports_boundary_of_each_component(self):
        self.assertIn("retail_shelf", self.text)

    def test_trace_on_a_fossil_material_says_why_there_is_no_credit(self):
        text = "\n".join(trace(self.study, "ldpe", "landfill"))
        self.assertIn("No biogenic carbon credit applied", text)

    def test_unknown_route_lists_what_is_available(self):
        with self.assertRaisesRegex(KeyError, "available"):
            trace(self.study, "biofilm", "rocket_disposal")


class TestChartLayout(unittest.TestCase):
    """Layout regressions: labels that collide or bars that vanish."""

    def setUp(self):
        self.results = evaluate_all(load_study())

    def test_axis_peak_ignores_an_order_of_magnitude_outlier(self):
        """One 240-wide range must not squash every other bar to a stub."""
        peak = _axis_peak(self.results)
        top = max(r.total for r in self.results)
        self.assertLess(peak, top * 3.0)
        self.assertGreaterEqual(peak, top)

    def test_axis_peak_still_covers_merely_wide_ranges(self):
        peak = _axis_peak(self.results)
        for row in self.results:
            self.assertLessEqual(row.total_high, peak, row.label)

    def test_no_row_is_offscale_once_scope_variants_left_the_ranges(self):
        """Every range now fits the axis -- that IS the fix, so pin it."""
        svg = render_svg(self.results, "t")
        self.assertNotIn('stroke-width="1.8"', svg)  # no chevron drawn

    def test_a_genuinely_huge_range_still_runs_offscale_and_states_its_number(self):
        """The off-scale machinery must survive, for when a range really is wild."""
        wild = evaluate_all(
            load_study(overrides=[{"path": "biofilm/component/zein", "high": 900.0}])
        )
        svg = render_svg(wild, "t")
        self.assertIn('stroke-width="1.8"', svg)
        biggest = max(r.total_high for r in wild)
        self.assertIn(f"{biggest:.2f}", svg)  # never silently clipped

    def test_svg_height_covers_every_row(self):
        """The last row must not fall off the bottom of the canvas."""
        import re

        svg = render_svg(self.results, "t")
        height = float(re.search(r'height="([0-9.]+)"', svg).group(1))
        ys = [float(m) for m in re.findall(r'y="([0-9.]+)"', svg)]
        self.assertLess(max(ys), height, "content extends past the SVG height")

    def test_each_material_keeps_its_own_hue(self):
        svg = render_svg(self.results, "t")
        for material_id in ("ldpe", "pva", "biofilm"):
            self.assertIn(f"--s-{material_id}", svg)


class TestCli(unittest.TestCase):
    def test_table_and_trace_and_scenarios_all_exit_clean(self):
        for argv in (
            ["--table"],
            ["--list-scenarios"],
            ["--compare"],
            ["--boundaries"],
            ["--sensitivity"],
            ["--trace", "biofilm/composting"],
            ["--scenario", "sargassum_route", "--table"],
            ["--set", "biofilm/component/zein=2.0", "--table"],
        ):
            with self.subTest(argv=argv):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(main(argv), 0)
                self.assertTrue(buf.getvalue().strip())

    def test_bad_arguments_exit_non_zero_without_a_traceback(self):
        for argv in (["--scenario", "nope"], ["--trace", "biofilm"], ["--trace", "x/y"]):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(argv), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
