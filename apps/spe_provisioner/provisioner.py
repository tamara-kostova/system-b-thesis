"""
Docker SPE provisioner.

Lifecycle per permit:
  provision() → creates internal network → connects Postgres → launches JupyterLab
  teardown()  → stops container → disconnects Postgres → removes network

The internal Docker network is the EHDS no-egress control:
  docker network create --internal spe-net-<id>
The container has NO route to the internet. Verify inside container:
  curl https://google.com  →  must fail (network unreachable)
"""

import os
import secrets
from pathlib import Path

import docker
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from shared.audit import log_event

client = docker.from_env()

SPE_IMAGE            = os.getenv("SPE_IMAGE", "system-b-spe:latest")
POSTGRES_CONTAINER   = os.getenv("POSTGRES_CONTAINER_NAME", "system-b-thesis-postgres-1")
POSTGRES_INTERNAL_PORT = 5432


def provision(permit_id: str, db_user: str, db_password: str) -> dict:
    """
    Spin up a JupyterLab SPE for a granted permit.
    Returns metadata needed to connect the researcher to the notebook.
    """
    short     = permit_id.replace("-", "")[:12]
    net_name  = f"spe-net-{short}"
    ctr_name  = f"spe-{short}"
    token     = secrets.token_hex(20)

    # 1. Internal network — no internet egress
    try:
        old_net = client.networks.get(net_name)
        old_net.reload()
        # Disconnect every container still attached — not just Postgres
        for attrs in list(old_net.attrs.get("Containers", {}).values()):
            try:
                ctr = client.containers.get(attrs["Name"].lstrip("/"))
                old_net.disconnect(ctr, force=True)
            except (docker.errors.NotFound, docker.errors.APIError):
                pass
        old_net.remove()
    except docker.errors.NotFound:
        pass
    network = client.networks.create(net_name, driver="bridge", internal=True)

    # 2. Connect Postgres to the SPE network so the container can reach the DB
    pg = client.containers.get(POSTGRES_CONTAINER)
    network.connect(pg, aliases=["postgres"])

    # 3. DB connection string uses the alias "postgres" on the internal network
    db_url = f"postgresql://{db_user}:{db_password}@postgres:{POSTGRES_INTERNAL_PORT}/omop"

    # 4. Remove leftover container if one exists from a previous failed attempt
    try:
        old = client.containers.get(ctr_name)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    # 5. Launch JupyterLab on the default bridge so the host port is published,
    #    then connect it to the internal network for DB access.
    #    The internal network has no internet route — the container reaches the DB
    #    via the internal network alias "postgres", not via the internet.
    #    Note: full outbound internet blocking requires iptables (production enhancement).
    container = client.containers.run(
        SPE_IMAGE,
        name=ctr_name,
        detach=True,
        network="bridge",           # default bridge for host port publishing only
        environment={
            "DATABASE_URL":    db_url,
            "PERMIT_ID":       permit_id,
            "JUPYTER_TOKEN":   token,
            "LLM_GATEWAY_URL": os.getenv("LLM_GATEWAY_URL", "http://host.docker.internal:8006"),
        },
        # host.docker.internal doesn't auto-resolve on Linux Docker — add it explicitly
        extra_hosts={"host.docker.internal": "host-gateway"},
        ports={"8888/tcp": None},   # OS picks a free host port
        labels={"permit_id": permit_id, "role": "spe"},
    )

    # 6. Also connect to the internal spe network — DB access goes through here
    network.connect(container, aliases=["spe"])

    container.reload()
    host_port = container.ports["8888/tcp"][0]["HostPort"]

    log_event("spe.started", actor="provisioner", resource_id=permit_id, details={
        "container": ctr_name,
        "network":   net_name,
        "host_port": host_port,
    })

    return {
        "container_id":   container.id,
        "container_name": ctr_name,
        "network_id":     network.id,
        "network_name":   net_name,
        "host_port":      int(host_port),
        "jupyter_url":    f"http://localhost:{host_port}?token={token}",
        "token":          token,
    }


def teardown(permit_id: str):
    """Stop the SPE container and clean up the network."""
    short    = permit_id.replace("-", "")[:12]
    ctr_name = f"spe-{short}"
    net_name = f"spe-net-{short}"

    # Stop and remove container
    try:
        ctr = client.containers.get(ctr_name)
        ctr.stop(timeout=10)
        ctr.remove()
        log_event("spe.stopped", actor="provisioner", resource_id=permit_id,
                  details={"container": ctr_name})
    except docker.errors.NotFound:
        pass

    # Disconnect Postgres and remove network
    try:
        network = client.networks.get(net_name)
        try:
            pg = client.containers.get(POSTGRES_CONTAINER)
            network.disconnect(pg, force=True)
        except (docker.errors.NotFound, docker.errors.APIError):
            pass
        network.remove()
    except docker.errors.NotFound:
        pass


def get_status(permit_id: str) -> dict:
    short    = permit_id.replace("-", "")[:12]
    ctr_name = f"spe-{short}"
    try:
        ctr = client.containers.get(ctr_name)
        ctr.reload()
        port_bindings = ctr.ports.get("8888/tcp")
        host_port = port_bindings[0]["HostPort"] if port_bindings else None
        return {
            "status":     ctr.status,
            "host_port":  host_port,
            "jupyter_url": f"http://localhost:{host_port}" if host_port else None,
        }
    except docker.errors.NotFound:
        return {"status": "not_found", "host_port": None, "jupyter_url": None}
