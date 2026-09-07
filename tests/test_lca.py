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
from lca_film.chart import render_svg  # noqa: E402
from lca_film.config import DEFAULT_INPUTS, load_study  # noqa: E402
from lca_film.confidence import Confidence, weakest  # noqa: E402
from lca_film.report import full_report  # noqa: E402

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

    def test_editing_an_input_moves_the_result_and_upgrades_the_tag(self):
        text = DEFAULT_INPUTS.read_text(encoding="utf-8")

        # Replace the zein placeholder with a hypothetical sourced figure.
        patched = text.replace(
            'value      = 3.00\nlow        = 1.00\nhigh       = 760.00\nconfidence = "placeholder"',
            'value      = 2.00\nlow        = 1.80\nhigh       = 2.20\n'
            'confidence = "literature"\nsource_override = true',
        ).replace(
            'source     = "NO CREDIBLE INDUSTRIAL FIGURE FOUND.',
            'source     = "Hypothetical sourced figure for the swap test.',
        )
        self.assertNotEqual(text, patched, "patch did not apply; inputs.toml changed shape")

        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write(patched)
            path = fh.name

        swapped = evaluate_all(load_study(path))
        biofilm_rows = [r for r in swapped if r.material.id == "biofilm"]
        self.assertTrue(biofilm_rows)
        # The zein placeholder is gone, so the mass-fraction placeholders are all
        # that remain -- the flag must persist, and the huge range must collapse.
        for row in biofilm_rows:
            self.assertLess(row.total_high, 20.0, row.label)
            self.assertTrue(row.is_placeholder_based, row.label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
