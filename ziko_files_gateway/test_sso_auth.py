import os
from pathlib import Path
import tempfile
import time
import unittest
import sso_auth

class SSOTests(unittest.TestCase):
    def setUp(self):
        self.key="12"*32
        self.uid="abcdef1234567890abcdef1234567890"
        self.path="/api/list?drive=Workspace&path="
    def test_valid_identity_and_replay(self):
        h=sso_auth.signed_headers(self.key,self.uid,"GET",self.path,nonce="a"*32)
        v=sso_auth.AssertionVerifier()
        self.assertEqual(v.verify(h,"GET",self.path,self.key),self.uid)
        with self.assertRaises(PermissionError):v.verify(h,"GET",self.path,self.key)
    def test_tampered_path_method_signature(self):
        h=sso_auth.signed_headers(self.key,self.uid,"GET",self.path)
        for method,path in (("POST",self.path),("GET","/api/drives")):
            with self.assertRaises(PermissionError):sso_auth.AssertionVerifier().verify(h,method,path,self.key)
    def test_expiry_and_malformed(self):
        old=sso_auth.signed_headers(self.key,self.uid,"GET",self.path,int(time.time())-500)
        with self.assertRaises(PermissionError):sso_auth.AssertionVerifier().verify(old,"GET",self.path,self.key)
        h=sso_auth.signed_headers(self.key,self.uid,"GET",self.path)
        h.pop("X-ZikoFiles-SSO-Signature")
        with self.assertRaises(PermissionError):sso_auth.AssertionVerifier().verify(h,"GET",self.path,self.key)
        self.assertIsNone(sso_auth.AssertionVerifier().verify({},"GET",self.path,self.key))
    def test_owner_enrollment_and_no_takeover(self):
        with tempfile.TemporaryDirectory() as d:
            r=sso_auth.RoleRegistry(Path(d)/"private"/"roles.json")
            self.assertIsNone(r.role(self.uid))
            self.assertEqual(r.enroll_owner(self.uid),"owner")
            self.assertEqual(r.enroll_owner(self.uid),"owner")
            self.assertEqual(r.role(self.uid),"owner")
            self.assertEqual(os.stat(r.path).st_mode & 0o777,0o600)
            with self.assertRaises(PermissionError):r.enroll_owner("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    def test_request_approval_and_revoke(self):
        with tempfile.TemporaryDirectory() as d:
            r=sso_auth.RoleRegistry(Path(d)/"private"/"roles.json")
            owner=self.uid
            viewer="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            self.assertEqual(r.request_viewer(viewer,"Tami"),"pending")
            self.assertEqual(r.request_viewer(viewer,"Tami"),"pending")
            self.assertEqual(len(r.view_for_owner()["pending"]),1)
            self.assertEqual(r.enroll_owner(owner),"owner")
            self.assertEqual(r.approve_viewer(viewer),"viewer")
            self.assertEqual(r.role(viewer),"viewer")
            self.assertEqual(r.role(owner),"owner")
            self.assertFalse(r.view_for_owner()["pending"])
            with self.assertRaises(PermissionError):r.approve_viewer(viewer)
            self.assertTrue(r.revoke_viewer(viewer))
            self.assertIsNone(r.role(viewer))
            with self.assertRaises(PermissionError):r.revoke_viewer(owner)
            self.assertEqual(os.stat(r.path).st_mode & 0o777,0o600)

    def test_pending_label_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            r=sso_auth.RoleRegistry(Path(d)/"roles.json")
            for label in ("x"+chr(10)+"y", "x"*65, 42):
                with self.assertRaises(ValueError):r.request_viewer(self.uid,label)
            for n in range(25):
                self.assertEqual(r.request_viewer(f"viewer{n:08d}","User"),"pending")
            with self.assertRaises(PermissionError):r.request_viewer("viewer99999999","User")

    def test_uid_validation(self):
        for bad in ("","a","x"*129,"../admin","x\\nyyyyyyyyy"):
            self.assertFalse(sso_auth.valid_id(bad))
            with self.assertRaises(ValueError):sso_auth.signed_headers(self.key,bad,"GET","/")

if __name__=="__main__":unittest.main()
