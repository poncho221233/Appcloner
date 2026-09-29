#!/usr/bin/env python3
"""
APK Advanced Cloner
Descompila, elimina permisos invasivos, cambia package/name, recompila y firma.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)

# Permisos invasivos a eliminar automáticamente
INVASIVE_PERMISSIONS = {
    "android.permission.READ_PHONE_STATE",
    "android.permission.READ_PHONE_NUMBERS",
    "android.permission.CALL_PHONE",
    "android.permission.ANSWER_PHONE_CALLS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.PROCESS_OUTGOING_CALLS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.GET_ACCOUNTS",
    "android.permission.READ_SMS",
    "android.permission.SEND_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.RECEIVE_MMS",
    "android.permission.RECEIVE_WAP_PUSH",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.BODY_SENSORS",
    "android.permission.ACTIVITY_RECOGNITION",
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.CHANGE_WIFI_STATE",
    "android.permission.BLUETOOTH",
    "android.permission.BLUETOOTH_ADMIN",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "com.google.android.gms.permission.AD_ID",
}


def run(cmd, cwd=None, check=True):
    print(f"→ {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=cwd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.stdout:
        print(result.stdout)
    if check and result.returncode != 0:
        raise RuntimeError(f"Comando falló ({result.returncode}): {' '.join(cmd)}")
    return result


def find_tool(name):
    path = shutil.which(name)
    if path:
        return path
    for c in [f"/usr/local/bin/{name}", f"/usr/bin/{name}", f"./tools/{name}", f"./tools/{name}.jar"]:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(f"No se encontró la herramienta: {name}")


def decompile(apk_path, out_dir):
    apktool = find_tool("apktool")
    run([apktool, "d", str(apk_path), "-o", str(out_dir), "-f"])


def remove_invasive_permissions(manifest_path):
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    removed = []

    for elem in list(root):
        if elem.tag == "uses-permission" or elem.tag.endswith("}uses-permission"):
            name = elem.get(f"{{{ANDROID_NS}}}name") or elem.get("name")
            if name in INVASIVE_PERMISSIONS:
                root.remove(elem)
                removed.append(name)

    for elem in list(root):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag in ("uses-permission-sdk-23", "uses-permission-sdk-m"):
            name = elem.get(f"{{{ANDROID_NS}}}name") or elem.get("name")
            if name in INVASIVE_PERMISSIONS:
                root.remove(elem)
                removed.append(name)

    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

    if removed:
        print(f"Permisos eliminados ({len(removed)}):")
        for p in sorted(set(removed)):
            print(f"  - {p}")
    else:
        print("No se encontraron permisos invasivos para eliminar.")


def change_package_name(manifest_path, new_package):
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    old_package = root.get("package")
    if not old_package:
        raise ValueError("No se encontró el atributo 'package' en AndroidManifest.xml")

    print(f"Package original : {old_package}")
    print(f"Nuevo package    : {new_package}")
    root.set("package", new_package)

    for elem in root.iter():
        for attr, value in list(elem.attrib.items()):
            if old_package in value:
                elem.set(attr, value.replace(old_package, new_package))

    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    return old_package


def change_app_name(strings_path, new_name):
    if not strings_path.exists():
        print(f"⚠ No se encontró {strings_path}")
        return
    content = strings_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<string\s+name="app_name"[^>]*>)(.*?)(</string>)',
        re.DOTALL | re.IGNORECASE
    )
    if pattern.search(content):
        new_content = pattern.sub(rf"\1{new_name}\3", content)
        strings_path.write_text(new_content, encoding="utf-8")
        print(f"Nombre de la app actualizado a: {new_name}")
    else:
        print("⚠ No se encontró 'app_name' en strings.xml")


def rebuild(decoded_dir, output_apk):
    apktool = find_tool("apktool")
    run([apktool, "b", str(decoded_dir), "-o", str(output_apk)])


def generate_keystore(keystore_path, alias="cloner", password="android"):
    if keystore_path.exists():
        return
    print("Generando keystore de depuración...")
    run([
        "keytool", "-genkeypair", "-v",
        "-keystore", str(keystore_path),
        "-alias", alias,
        "-keyalg", "RSA", "-keysize", "2048",
        "-validity", "10000",
        "-storepass", password, "-keypass", password,
        "-dname", "CN=APK Cloner Pro, OU=Dev, O=OpenSource, L=Internet, ST=Web, C=US"
    ])


def sign_apk(unsigned_apk, signed_apk, keystore, alias="cloner", password="android"):
    apksigner = shutil.which("apksigner")
    if apksigner:
        run([
            apksigner, "sign",
            "--ks", str(keystore),
            "--ks-key-alias", alias,
            "--ks-pass", f"pass:{password}",
            "--key-pass", f"pass:{password}",
            "--out", str(signed_apk),
            str(unsigned_apk)
        ])
    else:
        print("apksigner no encontrado, usando jarsigner...")
        run([
            "jarsigner", "-verbose",
            "-sigalg", "SHA256withRSA", "-digestalg", "SHA-256",
            "-keystore", str(keystore),
            "-storepass", password, "-keypass", password,
            str(unsigned_apk), alias
        ])
        shutil.move(str(unsigned_apk), str(signed_apk))


def zipalign_apk(apk_path):
    zipalign = shutil.which("zipalign")
    if not zipalign:
        print("⚠ zipalign no encontrado, se omite")
        return
    aligned = apk_path.with_suffix(".aligned.apk")
    run([zipalign, "-f", "-p", "4", str(apk_path), str(aligned)])
    shutil.move(str(aligned), str(apk_path))


def main():
    parser = argparse.ArgumentParser(description="APK Advanced Cloner")
    parser.add_argument("--apk", required=True, help="Ruta al APK original")
    parser.add_argument("--name", required=True, help="Nuevo nombre visible")
    parser.add_argument("--package", required=True, help="Nuevo package name")
    parser.add_argument("--output", default="cloned.apk", help="APK de salida")
    parser.add_argument("--workdir", default=None, help="Directorio temporal")
    args = parser.parse_args()

    apk_path = Path(args.apk).resolve()
    if not apk_path.is_file():
        print(f"ERROR: No se encuentra el APK: {apk_path}")
        return 1

    work_root = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="apkcloner_"))
    decoded_dir = work_root / "decoded"
    unsigned_apk = work_root / "unsigned.apk"
    keystore = work_root / "cloner.keystore"
    final_apk = Path(args.output).resolve()

    try:
        print("=" * 60)
        print("  APK Advanced Cloner")
        print("=" * 60)

        print("\n[1/6] Descompilando APK...")
        decompile(apk_path, decoded_dir)

        print("\n[2/6] Eliminando permisos invasivos...")
        manifest = decoded_dir / "AndroidManifest.xml"
        remove_invasive_permissions(manifest)

        print("\n[3/6] Actualizando package name...")
        change_package_name(manifest, args.package)

        print("\n[4/6] Actualizando nombre de la aplicación...")
        strings_xml = decoded_dir / "res" / "values" / "strings.xml"
        change_app_name(strings_xml, args.name)

        print("\n[5/6] Recompilando APK...")
        rebuild(decoded_dir, unsigned_apk)

        print("\n[6/6] Firmando APK...")
        generate_keystore(keystore)
        sign_apk(unsigned_apk, final_apk, keystore)
        zipalign_apk(final_apk)

        print("\n" + "=" * 60)
        print(f"✅ APK generado: {final_apk}")
        print(f"   Tamaño: {final_apk.stat().st_size / 1024 / 1024:.2f} MB")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
