# Setup guide

How to get RAHBAR running on your own machine, from a bare laptop to a working local environment. Covers Linux (Ubuntu), Windows with WSL 2, and macOS.

Estimated time: 45 to 90 minutes, most of it downloads.

> Nothing here needs a GPU. Nothing here needs a paid account.

## Contents

1. [What you need](#1-what-you-need)
2. [Platform notes](#2-platform-notes) (read the one for your OS first)
3. [Install the tools](#3-install-the-tools)
4. [Get the code and the Python environment](#4-get-the-code-and-the-python-environment)
5. [Run Ollama](#5-run-ollama)
6. [Verify your setup](#6-verify-your-setup)
7. [Download the corpus](#7-download-the-corpus)
8. [Start the cluster](#8-start-the-cluster)
9. [Build, deploy, index, ask](#9-build-deploy-index-ask)
10. [Everyday commands](#10-everyday-commands)
11. [Troubleshooting](#11-troubleshooting)

Architecture first, if you have not read it: [`architecture/architecture.md`](architecture/architecture.md).

---

## 1. What you need

| | Minimum | Comfortable |
| --- | --- | --- |
| RAM | 12 GB free | 16 GB or more (minikube 6 GB + Ollama models about 3 GB + your editor) |
| CPU | 4 cores | 6 cores or more |
| Disk | 25 GB free | 40 GB |
| Network | Needed for downloads and `make fetch` | |
| Accounts | GitHub (collaborator on this repo) | Docker Hub (only whoever owns CD) |

Tools and the versions this repository was developed with:

| Tool | Version | Used for |
| --- | --- | --- |
| Python | 3.12 | api, indexer, eval, tests |
| `make`, `git`, `curl` | any recent | everything |
| Tesseract OCR, Poppler | apt packages | the indexer's OCR and PDF to image |
| Docker Engine | 29.x | building images; minikube's driver |
| kubectl | 1.37.x | talking to the cluster |
| minikube | 1.39.0 | the local cluster |
| kustomize | 5.8.3 | `kustomize build` |
| kubeconform | 0.8.0 | manifest validation |
| Ollama | 0.40.x | local LLM and embeddings |

The same list, with install notes, is in the root [`requirements.txt`](../requirements.txt).

---

## 2. Platform notes

### Linux (Ubuntu 22.04 or 24.04)

The reference platform. Follow section 3 as written. The minikube IP is reachable directly from your shell.

### Windows with WSL 2 (recommended path on Windows)

Native Windows is not supported: the Makefile needs bash and the tools are Linux binaries. Do **everything** inside an Ubuntu WSL 2 distribution.

1. In PowerShell (administrator): `wsl --install -d Ubuntu-24.04`, then reboot and create your Linux user.
2. Give WSL enough memory. Create or edit `%UserProfile%\.wslconfig` on Windows:

   ```ini
   [wsl2]
   memory=10GB
   processors=4
   ```

   Then run `wsl --shutdown` in PowerShell and open Ubuntu again.
3. Enable systemd inside Ubuntu (Docker Engine and Ollama's service need it). In Ubuntu:

   ```bash
   sudo tee /etc/wsl.conf >/dev/null <<'EOF'
   [boot]
   systemd=true
   EOF
   ```

   Then `wsl --shutdown` in PowerShell and reopen Ubuntu.
4. **Work inside the Linux filesystem** (`~/projects/...`), never under `/mnt/c/...`. It is much faster, and file permissions and line endings behave.
5. Set line endings once: `git config --global core.autocrlf input`.
6. Choose how you run Docker:
   - **Docker Engine installed inside Ubuntu (recommended).** Follow section 3 like a normal Linux machine. The minikube IP is reachable from your WSL shell, and everything in this guide works as written.
   - **Docker Desktop with WSL integration.** Works, but the minikube IP is not reachable from WSL: run `minikube tunnel` in a second terminal and use `INGRESS_IP=127.0.0.1` with `make ask` and `make eval`.
7. Install Ollama **inside Ubuntu** (the Linux build), not the Windows app, so that the minikube network can reach it the same way as on Linux.

### macOS

Use Homebrew. The minikube docker driver does not expose the cluster IP, so you always run `minikube tunnel` (second terminal) and pass `INGRESS_IP=127.0.0.1`. Details in sections 3 and 9.

---

## 3. Install the tools

### 3.1 System packages (Ubuntu or WSL Ubuntu)

```bash
sudo apt update
sudo apt install -y make git curl zstd python3.12 python3.12-venv \
                    tesseract-ocr poppler-utils ca-certificates
python3 --version   # must show 3.12.x
```

macOS: `brew install make git python@3.12 tesseract poppler zstd`.

### 3.2 Docker

Ubuntu or WSL Ubuntu (Docker Engine):

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

Then **log out and back in** (on WSL: close the terminal, run `wsl --shutdown` in PowerShell, reopen). Check:

```bash
docker run --rm hello-world
```

Until the new group applies you can run any command as `sg docker -c "docker ps"`.

macOS: install Docker Desktop and start it.

### 3.3 kubectl, minikube, kustomize, kubeconform

Binaries go to `~/.local/bin` (no sudo). Make sure it is on your `PATH`:

```bash
mkdir -p ~/.local/bin
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

```bash
# kubectl
curl -fsSLo ~/.local/bin/kubectl "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x ~/.local/bin/kubectl

# minikube 1.39.0
curl -fsSLo ~/.local/bin/minikube https://github.com/kubernetes/minikube/releases/download/v1.39.0/minikube-linux-amd64
chmod +x ~/.local/bin/minikube

# kustomize 5.8.3
curl -fsSL https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv5.8.3/kustomize_v5.8.3_linux_amd64.tar.gz | tar -xz -C ~/.local/bin kustomize

# kubeconform 0.8.0
curl -fsSL https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-amd64.tar.gz | tar -xz -C ~/.local/bin kubeconform
```

Check: `kubectl version --client`, `minikube version`, `kustomize version`, `kubeconform -v`.

macOS: `brew install kubectl minikube kustomize kubeconform`.

Not needed locally: Trivy (CI only) and kind (CI only).

### 3.4 Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

macOS: `brew install ollama` or the app from <https://ollama.com>.

---

## 4. Get the code and the Python environment

```bash
git clone https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG.git
cd RAHBAR-Grounded-RAG
git checkout dev
make install        # creates .venv and installs api + indexer + dev tools
```

`make install` runs `python3 -m venv .venv` and installs `api/requirements-dev.txt` and `indexer/requirements-dev.txt`. You do not need to activate the venv for `make` targets; to use it by hand: `source .venv/bin/activate`.

Set your git identity if you have not:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
```

Read [`../CONTRIBUTING.md`](../CONTRIBUTING.md) before your first commit.

---

## 5. Run Ollama

The default setup runs the LLM and the embedding model on your laptop, outside the cluster. Pods reach it at `host.minikube.internal:11434`, so Ollama must listen on all interfaces, not just `127.0.0.1`.

```bash
# terminal A, leave it running
OLLAMA_HOST=0.0.0.0 ollama serve
```

If the installer already started a system service, stop it first so you do not have two servers (`sudo systemctl stop ollama`), then start it as above.

```bash
# terminal B, once
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Check:

```bash
curl -s http://localhost:11434/api/tags | head -c 300
```

> **Security.** `OLLAMA_HOST=0.0.0.0` exposes Ollama to every machine on your network and it has no authentication. Do it on a trusted network, or block the port from outside with your firewall, and stop it when you are not working: `pkill ollama`.

You can work on most of the project without Ollama (tests, stubs, manifests). You need it for the real pipeline and for `make eval` on the real corpus.

---

## 6. Verify your setup

```bash
make test           # api and indexer tests, no cluster, no model, no network
make lint           # ruff and mypy
make dev            # API with stubs and the chat UI on http://localhost:8000
```

Open <http://localhost:8000> and ask anything. You should get an answer labelled `(stub)` with three citations. Stop it with `Ctrl+C`.

Both `make test` and `make lint` must pass before you start.

---

## 7. Download the corpus

The documents are public FAST-NUCES files and are **not** in Git. `corpus/sources.yaml` lists them, `corpus/MANIFEST.md` records their SHA-256.

```bash
make fetch                          # downloads to corpus/raw/ (polite pause between files)
.venv/bin/python corpus/fetch.py --verify    # re-hashes against the manifest
```

You should have 9 files and a `corpus/raw/_index.json`. `corpus/raw/` is gitignored; never commit it.

Check that OCR works on the scanned policy:

```bash
tesseract --version
pdffonts corpus/raw/faculty-entrepreneurship-and-technical-start-ups-policy.pdf   # empty font list = scan
```

(The exact file name is whatever `make fetch` printed.)

---

## 8. Start the cluster

```bash
make cluster
```

This is: `minikube start --driver=docker --cni=calico --memory=6144 --cpus=4`, then enabling the `metrics-server` and `ingress` addons. Calico matters: the default network plugin accepts NetworkPolicy manifests and silently ignores them.

Check:

```bash
kubectl get nodes                       # one node, Ready
kubectl get pods -A                     # calico, ingress-nginx, metrics-server running
```

Stop and start without losing anything: `minikube stop` / `minikube start`. Throw it away: `minikube delete`.

Make sure minikube can reach Ollama:

```bash
minikube ssh "curl -s http://host.minikube.internal:11434/api/tags | head -c 200"
minikube ssh "grep host.minikube.internal /etc/hosts"     # the host IP; used in the NetworkPolicy (if it is not 192.168.49.1, edit the two cidr values in k8s/overlays/dev/kustomization.yaml)
```

If the first command prints nothing, Ollama is not listening on `0.0.0.0` or a firewall blocks it (see Troubleshooting).

---

## 9. Build, deploy, index, ask

> **Status.** The Kubernetes manifests, the Dockerfiles, `make corpus` and the real pipeline are being built (see [`WORKPLAN.md`](WORKPLAN.md)). The order below is the target and is the contract for the README. Each step is marked when it lands.

```bash
make images         # build api, indexer, ui and load them into minikube
make corpus         # create the namespace and corpus PVC, copy corpus/raw into it
make apply          # kubectl apply -k k8s/overlays/dev (the indexer Job runs once Chroma is up)
kubectl get pods -n rahbar -w
```

When `api` pods show `1/1 READY` the index exists. Ask a question:

```bash
make ask Q="What CGPA puts a student on academic warning?"
make ask Q="What are the hostel rules?"        # should decline
```

Optional, for hosted mode only (the key is never written to a file):

```bash
export LLM_API_KEY=...        # your free-tier key
make secret
```

The equivalent without make:

```bash
kubectl create secret generic rahbar-secret -n rahbar --from-literal=LLM_API_KEY="$LLM_API_KEY"
```

Ingress host. `make ask` and `make eval` send the `Host: rahbar.local` header for you. To use a browser, add the line from `echo "$(minikube ip) rahbar.local"` to `/etc/hosts` and open <http://rahbar.local>.

macOS, or Docker Desktop on Windows: run `minikube tunnel` in a second terminal and use `make ask INGRESS_IP=127.0.0.1 Q="..."`.

Re-index without a redeploy:

```bash
make index          # kubectl create job --from=cronjob/reindex ...
```

Evaluate against the real corpus:

```bash
make eval
```

---

## 10. Everyday commands

| Command | What it does |
| --- | --- |
| `make test` | Unit tests for api and indexer. Run before every push. |
| `make lint` | `ruff` and `mypy`. |
| `make dev` | API with stubs and the UI on <http://localhost:8000>. |
| `make dev-services` | Chroma on `localhost:8100` and Redis Stack on `6379` in Docker (`make dev-services-stop` removes them, `make dev-services-reset` also deletes their data). Until the desktop is re-logged: `sg docker -c "make dev-services"`. Prove them with `sg docker -c ".venv/bin/python scripts/verify_services.py"`. |
| `make check` | The submission checker (a lint, not a grader). |
| `make cluster` | Start minikube with the right options. |
| `make images` | Build and load the three images. Re-run after any code change you want in the cluster. |
| `make apply` | Apply the dev overlay. |
| `make index` | Re-run the indexer from the CronJob template. |
| `make ask Q="..."` | Ask through the Ingress. |
| `make eval` | Score `eval/golden.yaml` and apply the gate. |
| `kubectl get pods -n rahbar` | Status first. Then `kubectl describe pod`, then `kubectl logs`. |
| `kubectl logs deploy/api -n rahbar \| jq .` | JSON logs, readable. |
| `kubectl top pods -n rahbar` | Resource use (needs metrics-server). |
| `minikube stop` | Free RAM and CPU when you stop working. |

Diagnose in this order, always: `kubectl get pods`, `kubectl describe pod` (read the Events at the bottom), `kubectl logs` (add `--previous` for a crashed container).

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `permission denied` on `/var/run/docker.sock` | Your session predates the `docker` group | Log out and in (WSL: `wsl --shutdown`). Meanwhile `sg docker -c "<command>"`. |
| `make cluster` fails with a memory error | Not enough RAM for 6 GB | Close apps; lower `--memory` to 4096 temporarily; on WSL raise `memory=` in `.wslconfig`. |
| `ImagePullBackOff` on `rahbar-*` | minikube cannot see your laptop's images | `make images` (it runs `minikube image load`); keep `imagePullPolicy: IfNotPresent`. |
| api cannot reach Ollama | Ollama on `127.0.0.1`, or firewall, or the NetworkPolicy `ipBlock` has the wrong IP | `OLLAMA_HOST=0.0.0.0 ollama serve`; check `minikube ssh "grep host.minikube.internal /etc/hosts"` and put that IP in the dev overlay. |
| Every service name stops resolving after NetworkPolicy | Default-deny egress also blocks DNS | Allow egress to kube-dns on port 53, UDP and TCP, in `kube-system`. |
| `ui` can still reach `chroma` | Cluster started without Calico | `minikube delete`, then `make cluster`. |
| HPA shows `<unknown>/70%` | No `requests.cpu`, or metrics-server not ready | Add requests; `minikube addons enable metrics-server`; wait a minute. |
| Indexer `CrashLoopBackOff`, exit code 137 | OOMKilled: embedding uses more memory than serving | Raise the Job's memory limit, guided by `kubectl top pods`. |
| api `Running` but `0/1 READY` | Empty or missing collection, wrong probe path, or the embedding pin guardrail | `kubectl describe pod`, then `kubectl logs`. It is correct before the first index finishes. |
| `curl` to the Ingress times out (macOS, Docker Desktop) | The minikube IP is not reachable | `minikube tunnel` and `INGRESS_IP=127.0.0.1`. |
| `make fetch` fails for one file | The site changed or a link is down | It reports every failure and carries on. Re-run later; do not remove the pause between requests. |
| `tesseract: command not found` | Package missing | `sudo apt install tesseract-ocr poppler-utils`. |
| `make lint` complains about files you did not touch | Old caches | `rm -rf .ruff_cache api/.mypy_cache indexer/.mypy_cache` and retry. |
| Cannot push to `main` | Branch protection, on purpose | Push a branch and open a pull request. See `CONTRIBUTING.md`. |

Still stuck: copy the exact command, the full error, and the output of `kubectl get pods -n rahbar` and `kubectl describe pod <pod> -n rahbar` into the team chat or an issue.
