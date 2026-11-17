import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('submission_sync', Path(__file__).parents[1] / 'sync.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
URL = 'https://huggingface.co/Brownight/tabpfn-iv-adapter-v0.3'

def issue(n=1):
    return {'number': n, 'title': '[Method submission] Brownight/tabpfn-iv-adapter-v0.3', 'body': f'### Hugging Face model link\n{URL}\n\n### Research domain\niv\n\n{m.MARKER}', 'user': {'login': 'brownight'}, 'state': 'open', 'created_at': '2026-11-17T03:00:00Z', 'updated_at': '2026-11-17T03:00:00Z'}

class ArchiveTests(unittest.TestCase):
    def test_valid_link(self):
        self.assertEqual(m.parse_issue(issue())['huggingface_url'], URL)
        self.assertEqual(m.canonical_url(URL+'/'), URL)
        self.assertEqual(m.canonical_url(URL+'/tree/v0.3'), URL+'/tree/v0.3')
    def test_reject_unsafe_urls(self):
        for url in ['http://huggingface.co/a/b','https://huggingface.co.evil.test/a/b','https://huggingface.co@evil.test/a/b',URL+'?token=secret',URL+'#x',URL+'/../evil','https://huggingface.co/datasets/a','https://huggingface.co/spaces/a',URL+'\n$(bad)', 'javascript:alert(1)', URL+'/tree/../../main']:
            self.assertIsNone(m.canonical_url(url), url)
    def test_non_submission_ignored(self):
        for key,value in [('title','Other issue'),('body','unstructured'),('pull_request',{'url':'x'}),('number','../../main'),('user',{'login':'evil|cell'}),('created_at','unknown')]:
            i=issue();i[key]=value;self.assertIsNone(m.parse_issue(i),key)
    def test_unknown_domain_safe(self):
        i=issue();i['body']=i['body'].replace('\niv\n','\nevil\n');self.assertEqual(m.parse_issue(i)['domain'],'unspecified')
    def test_archive_idempotency_and_edit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);i=issue();m.write_archive([i],root)
            before={p.name:p.read_bytes() for p in (root/'received').iterdir()}
            m.write_archive([i],root);self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'received').iterdir()})
            i['state']='closed';m.write_archive([i],root)
            self.assertEqual(json.loads((root/'received/issue-000001.json').read_text())['status'],'closed')
            m.write_archive([],root);self.assertIn('Brownight/tabpfn', (root/'received/README.md').read_text())
    def test_test_record_separate(self):
        with tempfile.TemporaryDirectory() as d:
            i=issue();i['title']='[Method submission] [TEST] Brownight/tabpfn-iv-adapter-v0.3';root=Path(d);m.write_archive([i],root)
            self.assertTrue((root/'checks/issue-000001.json').exists())
            self.assertNotIn('Brownight/tabpfn', (root/'received/README.md').read_text())

if __name__ == '__main__': unittest.main()
