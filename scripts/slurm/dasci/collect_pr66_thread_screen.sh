#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail
RUN="${1:?pass OUTPUT from the launch receipt}"
RUN="$(realpath "${RUN}")"
case "${RUN}" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr66/screen-*) ;; *) exit 1 ;; esac
test -s "${RUN}/submission.txt"
JOB="$(sed -n 's/^PILOT_JOB=//p' "${RUN}/submission.txt")"
[[ "${JOB}" =~ ^[0-9]+$ ]]
if test -n "$(squeue -h -j "${JOB}" -o '%i')"; then
  echo '[ERROR] job still queued/running; no package produced' >&2; exit 1
fi
SHA="$(sed -n 's/^PLAN_SHA256=//p' "${RUN}/submission.txt")"
python3 scripts/evidence/package_pr66_pilot.py "${RUN}/plan" \
  --expected-plan-sha "${SHA}" --output "${RUN}/pr66_thread_evidence.tar.gz"
sacct -j "${JOB}" --parsable2 \
  --format=JobID,State,ExitCode,Elapsed,ElapsedRaw,TotalCPU,AllocCPUS,ReqMem,MaxRSS \
  | tee "${RUN}/sacct-final.txt"
sha256sum "${RUN}/pr66_thread_evidence.tar.gz" "${RUN}/sacct-final.txt"
printf 'REMOTE_PACKAGE=vrcelestino@dgx-dasci.ujaen.es:%s/pr66_thread_evidence.tar.gz\n' "${RUN}"
echo NO_NEW_OPTIMIZATION_NO_ZENODO_UPLOAD
