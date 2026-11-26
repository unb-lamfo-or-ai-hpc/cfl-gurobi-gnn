"""Explicit one-call native session; import performs no Gurobi initialisation."""

import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .audit import audit_point
from .contract import (
    ContractError,
    approved_contract,
    canonical_bytes,
    digest,
    load_bundle,
    require,
)
from .journal import durable_json, file_sha256, read_vector
from .matrix import NativeMatrix, streamed_identity
from .observer import NativeObserver, available
from .records import _validate_start


@dataclass(frozen=True)
class NativePermit:
    """A binding to external author authority, not a machine approval signature."""

    source_commit: str
    input_sha256: str
    approval_reference: str
    mode: str

    def validate(self, store, input_path):
        validate_reader_path(input_path)
        require(
            re.fullmatch(r"[0-9a-f]{40}", self.source_commit) is not None,
            "Exact source commit required",
        )
        require(
            re.fullmatch(r"[0-9a-f]{64}", self.input_sha256) is not None,
            "Stored input SHA256 required",
        )
        require(
            self.mode in ("primary", "technical_qualification"),
            "Unknown execution scope",
        )
        require(
            bool(self.approval_reference.strip()),
            "External author CLI approval reference required",
        )
        require(
            store.binding["source_commit"] == self.source_commit
            and store.binding["mode"] == self.mode
            and store.binding["input_sha256"] == self.input_sha256,
            "Permit/source/scope binding mismatch",
        )
        require(
            file_sha256(input_path) == self.input_sha256,
            "Stored input changed before native admission",
        )


def validate_reader_path(path, *, platform=None):
    resolved = Path(path).resolve()
    require(
        (platform or sys.platform) != "win32" or str(resolved).isascii(),
        "Windows native reader requires an ASCII model path; preserve bytes and input SHA when staging",
    )
    return resolved


def parameter_value(value):
    """Parameter infinity is a valid setting, distinct from missing measurements."""
    require(
        type(value) in (int, float, str, bool), "Unsupported native parameter value"
    )
    if type(value) is float:
        require(not math.isnan(value), "NaN is not a valid native parameter")
        if math.isinf(value):
            return "+Infinity" if value > 0 else "-Infinity"
    return value


class ParameterInventoryError(ContractError):
    """Safe context only, never a native message or parameter value."""

    def __init__(self, name, operation, error):
        super().__init__("Noncredential native parameter snapshot failed")
        self.parameter_name = name
        self.operation = operation
        self.original_exception_type = type(error).__name__
        code = getattr(error, "errno", None)
        self.errno = code if type(code) is int else None


def parameter_inventory(api, model):
    all_names = sorted(
        {
            getattr(api.GRB.Param, name)
            for name in dir(api.GRB.Param)
            if not name.startswith("_")
            and isinstance(getattr(api.GRB.Param, name), str)
        }
    )
    require(all_names, "Documented native parameter catalogue is unavailable")
    excluded = [name for name in all_names if private_parameter(name)]
    names = [name for name in all_names if name not in excluded]
    defaults, effective, types = {}, {}, {}
    for name in names:
        operation = "query_metadata"
        try:
            info = model.getParamInfo(name)
            require(
                len(info) == 6 and info[0] == name, "Native parameter metadata mismatch"
            )
            require(
                info[1] in (int, float, str, bool), "Unsupported native parameter type"
            )
            types[name] = info[1].__name__
            operation = "encode_default"
            defaults[name] = parameter_value(info[5])
            operation = "encode_effective"
            effective[name] = parameter_value(info[2])
        except Exception as error:
            raise ParameterInventoryError(name, operation, error) from error
    return {
        "scope": "documented_noncredential_model_parameters",
        "value_encoding": "typed_native_infinities_as_strings_v1_NaN_rejected",
        "parameter_types": types,
        "excluded_auth_transport_names_not_queried": excluded,
        "public_catalogue_names_sha256": digest(all_names),
        "parameter_names_sha256": digest(names),
        "defaults": defaults,
        "effective": effective,
        "defaults_sha256": digest(defaults),
    }


def private_parameter(name):
    upper = name.upper()
    return (
        upper.startswith(("WLS", "CS", "CLOUD", "TOKEN"))
        or any(part in upper for part in ("SECRET", "PASSWORD", "ACCESSID", "LICENSE"))
        or upper in {"COMPUTESERVER", "WORKERPOOL", "USERNAME", "TSPORT"}
    )


class NativeSession:
    """Fresh original model and a single durable-intent optimize invocation."""

    def __init__(self, api, path, permit, store, profile, policy, *, bundle_path=None):
        self.api, self.path, self.permit, self.store = api, path, permit, store
        self.profile, self.policy = profile, policy
        self.bundle_path = bundle_path
        self.environment = self.model = self.matrix = self.identity = None
        self.called = False
        self.start_installed = False
        self.phase = "not_admitted"

    def __enter__(self):
        self.phase = "permit_and_profile_validation"
        self.permit.validate(self.store, self.path)
        stage = self.store.binding["key"]["stage"]
        require(
            stage in approved_contract()["solver"]["profiles"], "Unknown native stage"
        )
        require(
            self.store.binding["key"]["seed"] == 42, "Native seed identity must be 42"
        )
        method = self.store.binding["key"]["method"]
        require(
            (stage == "evaluation" and method in ("B", "R", "G"))
            or (stage != "evaluation" and method is None),
            "Stage/method binding mismatch",
        )
        approved = approved_contract()["solver"]["profiles"][stage]
        if self.permit.mode == "primary":
            require(
                self.bundle_path is not None,
                "Primary admission requires the sealed bundle",
            )
            bundle = load_bundle(self.bundle_path)
            parent = self.store.binding["key"]["parent_id"]
            catalogue = next(
                (
                    row
                    for row in bundle["catalogue"]["parents"]
                    if row["original_id"] == parent
                ),
                None,
            )
            require(
                catalogue is not None
                and catalogue["stored_sha256"] == self.permit.input_sha256,
                "Primary input differs from the frozen catalogue",
            )
            key = self.store.binding["key"]
            require(
                any(
                    all(
                        row.get(name) == key.get(name)
                        for name in ("parent_id", "stage", "method", "seed")
                    )
                    for row in bundle["plan"]["cells"]
                ),
                "Call is outside the frozen primary plan",
            )
            require(
                canonical_bytes(self.profile) == canonical_bytes(approved),
                "Primary profile must match the approved stage exactly",
            )
        else:
            require(
                self.store.binding["key"]["parent_id"].startswith("QUAL_"),
                "Technical qualification must not reuse a research parent identity",
            )
            expected = {
                **approved,
                "Threads": 1,
                "TimeLimit": self.profile.get("TimeLimit"),
            }
            require(
                type(expected["TimeLimit"]) in (int, float)
                and 0 < expected["TimeLimit"] <= 10,
                "Bounded technical call must use at most ten native seconds",
            )
            require(
                canonical_bytes(self.profile) == canonical_bytes(expected),
                "Unreviewed technical profile override",
            )
        require(
            tuple(self.api.gurobi.version()) == (14, 0, 0),
            "Native version must be the admitted Gurobi14.0.0",
        )
        try:
            self.phase = "environment_creation"
            self.environment = self.api.Env(empty=True)
            # Native stdout is redirected by the owning supervisor. No LogFile,
            # LogToConsole or other undeclared model parameter is modified.
            self.phase = "environment_start"
            self.environment.start()
            self.phase = "original_model_read"
            self.model = self.api.read(str(self.path), env=self.environment)
            declared = {1: "MINIMIZE", -1: "MAXIMIZE"}[self.model.ModelSense]
            self.model.ModelSense = self.api.GRB.MINIMIZE
            self.model.update()
            require(
                self.model.SolCount == 0 and self.model.NumStart == 0,
                "Model contains a prior solution or Start",
            )
            for name, value in self.profile.items():
                self.phase = "native_parameter_overrides"
                self.model.setParam(name, value)
            self.phase = "original_matrix_identity"
            self.matrix = NativeMatrix(self.model, declared, self.api.GRB.INFINITY)
            self.identity = streamed_identity(self.matrix)
            require(
                self.store.append(
                    {"kind": "original_model_identity", "identity": self.identity},
                    critical=True,
                )
                is not None,
                "Original-model identity could not be retained",
            )
            self.phase = "native_parameter_inventory"
            self.parameters = parameter_inventory(self.api, self.model)
            expected = {**self.parameters["defaults"], **self.profile}
            require(
                self.parameters["effective"] == expected,
                "Undeclared native parameter change",
            )
            self.phase = "measurement_storage_admission"
            self.store.reserve_final_vectors(len(self.matrix.variables))
            admitted = self.store.append(
                {
                    "kind": "native_admission",
                    "identity": self.identity,
                    "parameter_inventory": self.parameters,
                    "audit_policy": self.policy.tolerances(),
                    "audit_policy_sha256": self.policy.sha256,
                },
                critical=True,
            )
            require(admitted is not None, "Native admission could not be retained")
            self.phase = "admitted_before_optimize"
            return self
        except BaseException:
            self.close()
            raise

    def install_start(self, start):
        self.phase = "partial_start_validation"
        require(not self.called, "Start must be installed before the sole main call")
        require(not self.start_installed, "External Start can be installed only once")
        require(
            self.store.binding["key"]["stage"] == "evaluation",
            "Only evaluation accepts an external Start",
        )
        method = self.store.binding["key"]["method"]
        _validate_start(start)
        require(
            start["key"] == self.store.binding["key"], "Start attempt binding mismatch"
        )
        require(
            start["model_sha256"] == self.identity["model_sha256"]
            and start["variable_order_sha256"]
            == self.identity["variable_order_sha256"],
            "Start original-model identity mismatch",
        )
        binary = [
            index
            for index, variable in enumerate(self.matrix.variables)
            if variable["domain"] == "B"
        ]
        require(
            start["original_variable_count"] == len(self.matrix.variables),
            "Start original-variable count mismatch",
        )
        require(
            start["binary_count"] == len(binary), "Start binary-domain count mismatch"
        )
        require(
            len(start["support"]) <= len(binary) // 10, "Start support cap exceeded"
        )
        require(
            len({item["position"] for item in start["support"]})
            == len(start["support"]),
            "Duplicate Start coordinate",
        )
        if method == "B":
            require(not start["support"], "B must have no external Start")
        else:
            require(
                start["frozen_policy_sha256"]
                == self.store.binding.get("frozen_start_policy_sha256"),
                "Start policy differs from the released frozen policy",
            )
            require(
                start["root_artifact_sha256"]
                == self.store.binding.get("root_artifact_sha256"),
                "Root guidance differs from the released artifact",
            )
            if method == "G":
                require(
                    start["predictor_sha256"]
                    == self.store.binding.get("predictor_sha256"),
                    "G predictor differs from the released validation selection",
                )
        for item in start["support"]:
            index = item["position"]
            require(
                type(index) is int and index in binary,
                "Start coordinate is not an original binary",
            )
            variable = self.matrix.variables[index]
            require(
                item["variable_name"] == variable["name"]
                and type(item["value"]) is int
                and item["value"] in (0, 1),
                "Start name/domain mismatch",
            )
            value = item["value"]
            require(
                item["lower_bound"] == variable["lower"]
                and item["upper_bound"] == variable["upper"],
                "Start bound metadata differs from the original model",
            )
            require(
                (variable["lower"] is None or variable["lower"] <= value)
                and (variable["upper"] is None or value <= variable["upper"]),
                "Start violates original bounds",
            )
        if start["support"]:
            for variable in self.matrix.native_variables:
                variable.Start = self.api.GRB.UNDEFINED
            for item in start["support"]:
                self.matrix.native_variables[item["position"]].Start = item["value"]
        self.model.update()
        require(
            self._current_identity() == self.identity,
            "Partial Start changed the mathematical model",
        )
        require(
            self.store.append({"kind": "partial_start", "record": start}, critical=True)
            is not None,
            "Start admission could not be retained",
        )
        self.start_installed = True
        self.phase = "admitted_before_optimize"

    def _current_identity(self):
        return streamed_identity(
            NativeMatrix(self.model, self.matrix.declared_sense, self.api.GRB.INFINITY)
        )

    def optimize_once(self):
        require(not self.called, "Automatic retry/repeated optimize is forbidden")
        stage = self.store.binding["key"]["stage"]
        require(
            stage != "evaluation" or self.start_installed,
            "Evaluation requires an explicit validated B/R/G Start record",
        )
        observer = NativeObserver(self.api, self.matrix, self.store, stage)
        self.phase = "durable_optimize_intent"
        self.store.optimize_intent(self.permit.approval_reference)
        self.called = True
        started = time.perf_counter()
        self.phase = "native_optimize"
        self.model.optimize(observer)
        wall = time.perf_counter() - started
        self.store.native_returned(int(self.model.Status))
        self.phase = "native_return_and_audit"
        require(
            self._current_identity() == self.identity,
            "Original model changed during native optimisation",
        )
        require(
            file_sha256(self.path) == self.permit.input_sha256,
            "Stored input changed during native call",
        )
        raw = {
            "native_status": int(self.model.Status),
            "native_runtime": available(float(self.model.Runtime)),
            "native_Work": available(float(self.model.Work)),
            "optimize_external_wall_seconds": wall,
            "native_primal": available(float(self.model.ObjVal))
            if self.model.SolCount
            else {"value": None, "missing_reason": "no_incumbent"},
            "native_bound": available(float(self.model.ObjBound)),
            "native_gap": available(float(self.model.MIPGap))
            if self.model.SolCount
            else {"value": None, "missing_reason": "no_incumbent"},
            "native_solution_count": int(self.model.SolCount),
            "observer": observer.summary(),
        }
        final = None
        if self.model.SolCount:
            values = [float(variable.X) for variable in self.matrix.native_variables]
            descriptor = self.store.put_vector(values, final=True)
            raw["final_vector"] = descriptor
            if descriptor["sha256"] is not None:
                final = audit_point(
                    self.matrix,
                    values,
                    self.policy,
                    native_objective=self.model.ObjVal,
                    identity=self.identity,
                )
                if final["audit"] is not None:
                    final["canonical_artifact"] = self.store.put_vector(
                        final["vector"], final=True
                    )
                final.pop("vector", None)
        root = None
        if observer.captured_root:
            descriptor = observer.captured_root["root_vector"]
            root = audit_point(
                self.matrix,
                read_vector(self.store.folder, descriptor),
                self.policy,
                continuous=True,
                identity=self.identity,
            )
            root.pop("vector", None)
        result = {
            "schema_version": "mvp3-s1b-native-v1",
            "binding_sha256": self.store.binding_sha256,
            "identity": self.identity,
            "parameters": self.parameters,
            "native": raw,
            "final_audit": final,
            "root_audit": root,
            "call_returned": True,
            "scientific_population": self.permit.mode,
        }
        durable_json(self.store.folder / "native-result.json", result)
        self.phase = "result_persisted"
        return result

    def close(self):
        try:
            if self.model is not None:
                self.model.dispose()
        finally:
            self.model = None
            if self.environment is not None:
                self.environment.dispose()
            self.environment = None

    def __exit__(self, exc_type, exc, traceback):
        self.close()
