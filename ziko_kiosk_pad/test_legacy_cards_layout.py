import pathlib,re,unittest
ROOT=pathlib.Path(__file__).parent
class Safari9CardsRegression(unittest.TestCase):
 def test_legacy_absolute_fallback_is_active(self):
  css=(ROOT/'pad_copy/pad-lights-014.css').read_text()
  self.assertRegex(css,r'\.lk-pad\s*\{[^}]*position:\s*relative')
  self.assertRegex(css,r'\.lk-pad\s+\.lkp-area\s*\{[^}]*position:\s*absolute')
  self.assertRegex(css,r'\.lk-pad\s+\.lkp-cards[^{}]*\{[^}]*display:\s*block')
  self.assertRegex(css,r'\.lk-pad\s+\.lkp-cards\s*>\s*\.lkp-card\s*\{[^}]*position:\s*absolute')
 def test_six_cards_and_corridor_have_coordinates(self):
  css=(ROOT/'pad_copy/pad-lights-014.css').read_text()
  for i in range(1,7): self.assertRegex(css,r'\.lkp-cards\s*>\s*\.lkp-card:nth-child\('+str(i)+r'\)')
  self.assertIn('.lkp-cards.is-four>.lkp-card:nth-child(4)',css)
  self.assertIn('height:100%',css)
 def test_production_assets_and_routes_are_fork_only(self):
  js=(ROOT/'pad_copy/pad-lights-014.js').read_text()
  secure=(ROOT/'secure.py').read_text()
  self.assertIn('/kiosk-pad/assets/pad-lights-014.js',secure)
  self.assertIn("var CSS_URL='/kiosk-pad/assets/pad-lights-014.css'",js)
  self.assertIn('"pad-lights-014.css"',secure)
  self.assertIn('"pad-lights-014.js"',secure)
 def test_original_miix_assets_are_unchanged(self):
  for path in ('kiosk-lights-copy.es5.js','kiosk-thermostat-copy.es5.js'):
   self.assertTrue((ROOT/'pad_copy'/path).exists())
if __name__=='__main__':unittest.main()
