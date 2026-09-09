# Optional local Kubernetes demo

These files do not provision cloud resources or publish a container image.

Build `inferencemesh:0.2.0` locally and load it into the existing local cluster
(for example, `kind load docker-image inferencemesh:0.2.0`). The deployment uses
`imagePullPolicy: Never`; it does not reference a nonexistent published image.

Create the `inferencemesh` namespace and an `inferencemesh-gateway` secret in it
with distinct `api-key` and `metrics-key` values. Supply secrets outside version control.
Apply the network policy and gateway manifests only after these prerequisites.

This is an explicit deterministic demo profile. Its one replica and Recreate update
strategy match the current per-process quotas; upgrades incur downtime. The example
does not claim high availability. The disruption budget permits voluntary eviction.

The default-deny egress policy suits the deterministic profile. Real HTTP serving
requires an explicit network policy allowing DNS and the chosen upstream destination.
Do not simply disable network policy to make an arbitrary external endpoint reachable.
Prefer the documented loopback Ollama setup for free local model evaluation.

An actual Docker build and Kubernetes run are separate validation steps. The presence
of these definitions is not proof either was performed.
