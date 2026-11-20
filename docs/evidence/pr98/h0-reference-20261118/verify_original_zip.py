"""Qualify H0 from a local original ZIP against the official remote directory."""
import argparse
import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("original_zip", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
original = args.original_zip
directory = json.loads(Path(__file__).with_name("official-zip-directory.json").read_text())
before = original.stat()
assert before.st_size == directory["official_zip_bytes"]
with zipfile.ZipFile(original) as archive:
    actual = [{"name":z.filename,"bytes":z.file_size,"compressed_bytes":z.compress_size,
               "compression":z.compress_type,"crc32":f"{z.CRC:08x}","header_offset":z.header_offset}
              for z in archive.infolist()]
    assert actual == directory["entries"], "official_directory_mismatch"
    name = "CFL_hard_instance/LP/CFL_hard_instance_0.lp"
    member = archive.getinfo(name)
    h = hashlib.sha256()
    size = 0
    with archive.open(member) as stream:
        for chunk in iter(lambda: stream.read(8*1024**2), b""):
            size += len(chunk)
            assert size <= 512*1024**2
            h.update(chunk)
    assert size == member.file_size
print("OFFICIAL_DIRECTORY_AND_H0_CRC_OK",flush=True)
zipped = hashlib.sha256()
with original.open("rb") as stream:
    for chunk in iter(lambda: stream.read(8*1024**2), b""):
        zipped.update(chunk)
after = original.stat()
assert (before.st_size,before.st_mtime_ns) == (after.st_size,after.st_mtime_ns)
result = {
    "schema_version":1,"parent":"CFL_hard_instance_0",
    "reference_origin":"independent_original_ZIP_with_official_remote_directory_match",
    "official_index_url":"https://github.com/thuiar/MILPBench/blob/main/Benchmark%20Datasets/README.md",
    "official_file_id":"13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0",
    "official_zip_bytes":before.st_size,"local_original_zip_sha256":zipped.hexdigest(),
    "official_directory_exact_match":True,"official_directory_entries":len(actual),
    "official_directory_receipt_sha256":hashlib.sha256(Path("official_zip_directory.json").read_bytes()).hexdigest(),
    "member":name,"member_compressed_bytes":member.compress_size,
    "member_header_offset":member.header_offset,"member_crc32":f"{member.CRC:08x}",
    "crc_verified":True,"decoded_bytes":size,"decoded_sha256":h.hexdigest(),
    "query_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
    "optimization_calls":0,"pickle_deserializations":0,
    "full_remote_member_download":"blocked_by_Google_Drive_download_quota",
    "independence_scope":"LP inside original local ZIP checked against official directory; not a second hash of the installed HPC LP",
}
with args.output.open("x",encoding="utf8") as stream:
    stream.write(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps(result,indent=2))
