import pathlib,re,unittest
P=pathlib.Path(__file__).parent
class LegacyViewportTests(unittest.TestCase):
 def test_explicit_root_viewport_height(self):
  js=(P/'pad-lights-015.js').read_text()
  self.assertIn('window.innerHeight',js)
  self.assertIn('style="height:',js)
  self.assertIn('min-height:',js)
 def test_css_viewport_fallback_and_area(self):
  css=(P/'pad-lights-015.css').read_text()
  self.assertIn('height:100vh!important',css)
  self.assertIn('min-height:100vh!important',css)
  self.assertIn('position:absolute!important',css)
 def test_diagnostic_reports_root_and_area(self):
  js=(P/'pad-lights-015.js').read_text()
  for marker in ('lights-015-', 'root:', 'viewport:', 'area:', 'tile:'):self.assertIn(marker,js)
 def test_fork_only_registration(self):
  secure=(P/'secure.py').read_text();docker=(P/'Dockerfile').read_text();config=(P/'config.yaml').read_text()
  self.assertIn('pad-lights-015.js',secure)
  self.assertIn('pad-lights-015.css',secure)
  self.assertIn('pad-lights-015.js pad-lights-015.css',docker)
  self.assertIn('version: "0.3.15"',config)
if __name__=='__main__':unittest.main()
