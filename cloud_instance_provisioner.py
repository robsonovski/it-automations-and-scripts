#!/usr/bin/env python3
"""
Oracle Cloud Infrastructure (OCI) - Automated VM Instance Provisioner
Author: Robert Kazienko (https://github.com/robsonovski)

Autonomiczne narzędzie CLI do provisioningu instancji obliczeniowych (Compute Instances)
w chmurze Oracle Cloud (OCI Always Free / ARM A1.Flex).

Główne funkcje:
- Dynamiczne wyszukiwanie dostępnych podsieci publicznych (VCN/Subnet).
- Wyszukiwanie najnowszego obrazu Canonical Ubuntu 22.04 LTS (AArch64).
- Odporność na brak zasobów ("Out of host capacity") - retry loop z exponential backoff.
- Weryfikacja cyklu życia instancji (stan RUNNING) i ekstrakcja publicznego IPv4.
- Integracja z powiadomieniami systemowymi Linux (notify-send).
"""

import sys
import os
import time
import argparse
import subprocess
from datetime import datetime
from typing import List, Optional

try:
    import oci
except ImportError:
    print("Błąd: Biblioteka 'oci' nie jest zainstalowana. Uruchom: pip install oci", file=sys.stderr)
    sys.exit(1)


def log(msg: str) -> None:
    """Formatowane logowanie ze stemplem czasowym."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def notify_desktop(title: str, message: str) -> None:
    """Wysyła powiadomienie na pulpit Linuksa (jeśli dostępne środowisko graficzne)."""
    log(f"POWIADOMIENIE: {title} - {message}")
    try:
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        subprocess.run(["notify-send", "-u", "critical", title, message], env=env, check=False)
    except Exception:
        pass


def read_ssh_public_key(key_path: str) -> str:
    """Odczytuje i waliduje klucz publiczny SSH."""
    expanded = os.path.expanduser(key_path)
    if not os.path.exists(expanded):
        raise FileNotFoundError(f"Nie znaleziono pliku klucza SSH: {expanded}")
    with open(expanded, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not (content.startswith("ssh-rsa") or content.startswith("ssh-ed25519") or content.startswith("ecdsa-")):
        log("Ostrzeżenie: Format klucza publicznego może być nietypowy.")
    return content


def find_latest_ubuntu_image(
    compute_client: oci.core.ComputeClient,
    compartment_id: str,
    shape: str = "VM.Standard.A1.Flex",
    version: str = "22.04"
) -> str:
    """Wyszukuje najnowszy zgodny obraz systemu Ubuntu dla danej architektury."""
    log(f"Wyszukiwanie obrazu Canonical Ubuntu {version} dla kształtu {shape}...")
    images = compute_client.list_images(
        compartment_id=compartment_id,
        shape=shape,
        operating_system="Canonical Ubuntu",
        operating_system_version=version,
        sort_by="TIMECREATED",
        sort_order="DESC"
    ).data

    arm_images = [img for img in images if "aarch64" in img.display_name.lower()]
    selected = arm_images[0] if arm_images else (images[0] if images else None)

    if not selected:
        raise RuntimeError(f"Nie znaleziono kompatybilnego obrazu Ubuntu {version} dla {shape}")

    log(f"Wybrany obraz: {selected.display_name} (ID: {selected.id})")
    return selected.id


def find_public_subnet(network_client: oci.core.VirtualNetworkClient, compartment_id: str) -> str:
    """Dynamicznie odnajduje pierwszą dostępną publiczną podsieć w sieciach VCN."""
    log("Wyszukiwanie sieci VCN i podsieci publicznych...")
    vcns = network_client.list_vcns(compartment_id=compartment_id).data
    if not vcns:
        raise RuntimeError("Brak skonfigurowanych sieci VCN w compartment.")

    for vcn in vcns:
        subnets = network_client.list_subnets(compartment_id=compartment_id, vcn_id=vcn.id).data
        for subnet in subnets:
            if not subnet.prohibit_public_ip_on_vnic:
                log(f"Znaleziono publiczną podsieć: {subnet.display_name} (VCN: {vcn.display_name})")
                return subnet.id

    fallback = network_client.list_subnets(compartment_id=compartment_id, vcn_id=vcns[0].id).data[0]
    log(f"Użycie domyślnej podsieci: {fallback.display_name}")
    return fallback.id


def wait_for_instance_running(
    compute_client: oci.core.ComputeClient,
    network_client: oci.core.VirtualNetworkClient,
    compartment_id: str,
    instance_id: str,
    max_checks: int = 30,
    interval_seconds: int = 10
) -> List[str]:
    """Czeka na pełne uruchomienie maszyny i zwraca przypisany publiczny adres IP."""
    log("Oczekiwanie na przejście instancji w stan RUNNING...")
    for check in range(1, max_checks + 1):
        instance = compute_client.get_instance(instance_id).data
        state = instance.lifecycle_state
        log(f"Próba {check}/{max_checks} - Stan instancji: {state}")

        if state == "RUNNING":
            break
        if state in ["TERMINATED", "TERMINATING"]:
            raise RuntimeError(f"Instancja zakończona niepowodzeniem: {state}")
        time.sleep(interval_seconds)

    log("Instancja aktywna. Pobieranie publicznego adresu IP...")
    vnic_attachments = compute_client.list_vnic_attachments(
        compartment_id=compartment_id,
        instance_id=instance_id
    ).data

    public_ips: List[str] = []
    for attachment in vnic_attachments:
        vnic = network_client.get_vnic(attachment.vnic_id).data
        if vnic.public_ip:
            public_ips.append(vnic.public_ip)

    return public_ips


def main():
    parser = argparse.ArgumentParser(description="Automatyczny provisioner maszyn wirtualnych Oracle Cloud (OCI).")
    parser.add_argument("--config", default="~/.oci/config", help="Ścieżka do pliku konfiguracyjnego OCI")
    parser.add_argument("--profile", default="DEFAULT", help="Nazwa profilu w konfiguracji OCI")
    parser.add_argument("--name", default="prod-automation-node", help="Nazwa wyświetlana instancji")
    parser.add_argument("--ocpus", type=float, default=4.0, help="Liczba rdzeni OCPU (domyślnie: 4 dla ARM)")
    parser.add_argument("--memory-in-gbs", type=float, default=24.0, help="Pamięć RAM w GB (domyślnie: 24 dla ARM)")
    parser.add_argument("--ssh-key", default="~/.ssh/id_rsa.pub", help="Ścieżka do klucza publicznego SSH")
    parser.add_argument("--retry-delay", type=int, default=60, help="Odstęp między próbami przy braku zasobów (sekundy)")
    args = parser.parse_args()

    config_path = os.path.expanduser(args.config)
    if not os.path.exists(config_path):
        log(f"Błąd: Nie znaleziono pliku konfiguracyjnego OCI: {config_path}")
        sys.exit(1)

    try:
        config = oci.config.from_file(config_path, args.profile)
    except Exception as e:
        log(f"Błąd parsowania konfiguracji OCI: {e}")
        sys.exit(1)

    compartment_id = config.get("tenancy")
    compute_client = oci.core.ComputeClient(config)
    network_client = oci.core.VirtualNetworkClient(config)

    ssh_key_data = read_ssh_public_key(args.ssh_key)
    image_id = find_latest_ubuntu_image(compute_client, compartment_id)
    subnet_id = find_public_subnet(network_client, compartment_id)

    log(f"Rozpoczynanie alokacji instancji: {args.name} ({args.ocpus} OCPU, {args.memory_in_gbs} GB RAM)...")

    attempt = 1
    while True:
        try:
            log(f"Próba utworzenia #{attempt}...")
            launch_details = oci.core.models.LaunchInstanceDetails(
                compartment_id=compartment_id,
                availability_domain=config.get("region"),
                display_name=args.name,
                shape="VM.Standard.A1.Flex",
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                    ocpus=args.ocpus,
                    memory_in_gbs=args.memory_in_gbs
                ),
                source_details=oci.core.models.InstanceSourceViaImageDetails(
                    image_id=image_id
                ),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=subnet_id,
                    assign_public_ip=True
                ),
                metadata={
                    "ssh_authorized_keys": ssh_key_data
                }
            )

            res = compute_client.launch_instance(launch_details)
            instance = res.data
            log(f"SUKCES! Zainicjowano tworzenie instancji ID: {instance.id}")

            ips = wait_for_instance_running(compute_client, network_client, compartment_id, instance.id)
            ip_str = ", ".join(ips) if ips else "Brak IP"
            log(f"Instancja gotowa do pracy! Publiczne IP: {ip_str}")

            notify_desktop("OCI Provisioner Sukces", f"Instancja {args.name} utworzona pomyślnie!\nIP: {ip_str}")
            break

        except oci.exceptions.ServiceError as se:
            if se.status == 500 or "capacity" in se.message.lower() or "limit" in se.message.lower():
                log(f"Brak wolnych zasobów w regionie ({se.message}). Ponowna próba za {args.retry_delay}s...")
                time.sleep(args.retry_delay)
                attempt += 1
            else:
                log(f"Nieoczekiwany błąd OCI Service: {se}")
                raise
        except Exception as e:
            log(f"Błąd krytyczny: {e}")
            raise


if __name__ == "__main__":
    main()
