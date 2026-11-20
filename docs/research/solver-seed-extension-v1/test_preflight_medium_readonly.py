"""Synthetic bounded-reader tests; never access the HPC or import a solver."""
import ast
import gzip
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("readonly_preflight",Path(__file__).with_name("preflight_medium_readonly.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
LP=b"Maximize\n x0 + 2 x1 + 0.5 x2\nSubject To\n R0: x0 + x1 >= 1\n R1: x2 - 800 x1 <= 0\nBounds\n x0 <= 1\n x2 <= 1\nBinaries\n x1\nEnd\n"

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);self.out=self.root/"evidence";self.out.mkdir()
        folder=self.root/"cfl-gurobi-gnn/data/raw/MILPBench/CFL/CFL_medium_instance/LP";folder.mkdir(parents=True)
        self.paths={}
        for parent in m.PARENTS:
            p=folder/(parent+".lp.gz");p.write_bytes(gzip.compress(LP,mtime=0));self.paths[parent]=p
        expected={p:m.digest(self.paths[p],m.Budget()) for p in m.EXPECTED}
        patcher=patch.object(m,"EXPECTED",expected);patcher.start();self.addCleanup(patcher.stop)
    def collect(self,budget=None):return m.collect(self.root,self.out,budget or m.Budget(),{"fixture":True})
    def test_six_files_hashes_and_structure_without_original_changes(self):
        before={p:p.read_bytes() for p in self.paths.values()}
        archive,report=self.collect()
        self.assertEqual(sum(r["readonly_preflight_complete"] for r in report["rows"]),6)
        self.assertEqual(report["rows"][0]["structure"]["variables_observed"],3)
        self.assertEqual(report["rows"][0]["structure"]["binary_variables_declared"],1)
        self.assertEqual(report["rows"][0]["structure"]["linear_rows_observed"],2)
        self.assertEqual(report["rows"][0]["structure"]["linear_nonzero_terms_observed"],4)
        self.assertFalse(report["execution_admitted"])
        for p,raw in before.items():self.assertEqual(p.read_bytes(),raw)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(set(z.namelist()),{"preflight.json","input-paths.private.json","manifest.json"})
            manifest=json.loads(z.read("manifest.json"))
            self.assertTrue(all(m.hashlib.sha256(z.read(k)).hexdigest()==v for k,v in manifest["sha256"].items()))
    def test_missing_file_disclosed_no_replacement(self):
        self.paths[m.PARENTS[0]].unlink();_,r=self.collect()
        self.assertIn("original_missing_in_two_layouts",r["rows"][0]["issues"])
        self.assertFalse(self.paths[m.PARENTS[0]].exists())
    def test_ambiguous_plain_and_compressed_not_selected(self):
        self.paths[m.PARENTS[0]].with_suffix("").write_bytes(LP);_,r=self.collect()
        self.assertEqual(r["rows"][0]["issues"],["ambiguous_original_paths"])
    def test_historical_hash_mismatch_blocks_binding(self):
        self.paths["CFL_medium_instance_13"].write_bytes(gzip.compress(LP+b"\n",mtime=0));_,r=self.collect()
        a=next(x for x in r["rows"] if x["parent"].endswith("_13"))
        self.assertFalse(a["historical_digest_match"]);self.assertIn("historical_original_digest_mismatch",a["issues"])
    def test_unknown_syntax_is_not_declared_valid(self):
        self.paths[m.PARENTS[0]].write_bytes(gzip.compress(LP.replace(b"x0 + 2 x1",b"[ x0 ^ 2 ] + 2 x1"),mtime=0));_,r=self.collect()
        self.assertFalse(r["rows"][0]["readonly_preflight_complete"])
        self.assertNotIn("structure",r["rows"][0])
    def test_corrupt_gzip_is_captured(self):
        self.paths[m.PARENTS[0]].write_bytes(b"not gzip");_,r=self.collect()
        self.assertIn("BadGzipFile",r["rows"][0]["issues"])
    def test_variable_index_budget(self):
        with self.assertRaisesRegex(ValueError,"variable_index_budget"):
            m.summarize(io.BytesIO(LP.replace(b"x2",b"x2000000")),m.Budget())
    def test_line_limit(self):
        with patch.object(m,"MAX_LINE",5):
            with self.assertRaisesRegex(ValueError,"line_size_budget"):m.summarize(io.BytesIO(LP),m.Budget())
    def test_time_budget_produces_partial_report(self):
        _,r=self.collect(m.Budget(seconds=-1))
        self.assertTrue(all("time_budget_exceeded" in x["issues"] for x in r["rows"]))
        self.assertFalse(any(x["readonly_preflight_complete"] for x in r["rows"]))
    def test_scope_escape(self):
        with self.assertRaisesRegex(ValueError,"outside_data_root"):
            m.safe(Path(__file__),self.root)
    def test_output_must_already_exist(self):
        with self.assertRaises(FileNotFoundError):m.collect(self.root,self.root/"new",m.Budget(),{})
        self.assertFalse((self.root/"new").exists())
    def test_exclusive_archive_preserves_previous_file(self):
        with patch.object(m.uuid,"uuid4",return_value=type("ID",(),{"hex":"fixed"})()):
            p,_=self.collect();raw=p.read_bytes()
            with self.assertRaises(FileExistsError):self.collect()
            self.assertEqual(p.read_bytes(),raw)
    def test_nonfinite_coefficient_rejected(self):
        with self.assertRaisesRegex(ValueError,"nonfinite_coefficient"):
            m.summarize(io.BytesIO(LP.replace(b"2 x1",b"1e999 x1")),m.Budget())
    def test_no_execution_or_mutation_apis(self):
        t=ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
        imports={a.name.split(".")[0] for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names}
        self.assertFalse(imports&{"gurobipy","torch","numpy","pickle","pr89_cpu_workflow"})
        calls={n.func.attr for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls&{"optimize","mkdir","unlink","remove","rename","terminate","load","loads_pickle"})
        subs=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="check_output"]
        self.assertEqual(len(subs),1);self.assertEqual(subs[0].args[0].elts[0].value,"git")

if __name__=="__main__":unittest.main()
