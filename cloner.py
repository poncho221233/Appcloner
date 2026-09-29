#!/usr/bin/env python3
"""
APK Advanced Cloner
Descompila, elimina permisos invasivos, ajusta Manifest para instalación,
cambia nombre visible, recompila con aapt2 --force-all, alinea y firma v1+v2+v3.
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
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag in ("uses-permission", "uses-permission-sdk-23", "uses-permission-sdk-m"):
            name = elem.get(f"{{{ANDROID_NS}}}name") or elem.get("name")
            if name in INVASIVE_PERMISSIONS:
                root.remove(elem)
                removed.append(name)

    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

    if removed:
        print(f"Permisos eliminados ({len(set(removed))}):")
        for p in sorted(set(removed)):
            print(f"  - {p}")
    else:
        print("No se encontraron permisos invasivos para eliminar.")


def fix_manifest_for_install(manifest_path):
    """Ajustes críticos para que Android acepte la instalación."""
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    app = root.find("application")
    if app is not None:
        # Forzar extractNativeLibs="true" (evita fallos con .so)
        app.set(f"{{{ANDROID_NS}}}extractNativeLibs", "true")
        # Asegurar testOnly="false"
        if f"{{{ANDROID_NS}}}testOnly" in app.attrib:
            del app.attrib[f"{{{ANDROID_NS}}}testOnly"]
        app.set(f"{{{ANDROID_NS}}}testOnly", "false")

    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    print("Manifest ajustado: extractNativeLibs=true, testOnly=false")


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
    run([
        apktool, "b",
        "--use-aapt2",
        "--force-all",
        str(decoded_dir),
        "-o", str(output_apk)
    ])


def zipalign_apk(input_apk, output_apk):
    zipalign = shutil.which("zipalign")
    if not zipalign:
        raise RuntimeError("zipalign no encontrado")
    run([zipalign, "-f", "-p", "4", str(input_apk), str(output_apk)])


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


def sign_apk(aligned_apk, signed_apk, keystore, alias="cloner", password="android"):
    apksigner = shutil.which("apksigner")
    if not apksigner:
        raise RuntimeError("apksigner no encontrado")

    run([
        apksigner, "sign",
        "--verbose",
        "--ks", str(keystore),
        "--ks-key-alias", alias,
        "--ks-pass", f"pass:{password}",
        "--key-pass", f"pass:{password}",
        "--min-sdk-version", "21",
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--out", str(signed_apk),
        str(aligned_apk)
    ])

    print("Verificando firma...")
    run([apksigner, "verify", "--verbose", str(signed_apk)])


def main():
    parser = argparse.ArgumentParser(description="APK Advanced Cloner")
    parser.add_argument("--apk", required=True, help="Ruta al APK original")
    parser.add_argument("--name", required=True, help="Nuevo nombre visible")
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
    aligned_apk = work_root / "aligned.apk"
    keystore = work_root / "cloner.keystore"
    final_apk = Path(args.output).resolve()

    try:
        print("=" * 60)
        print("  APK Advanced Cloner (aapt2 + force-all + v2/v3)")
        print("=" * 60)

        print("\n[1/7] Descompilando APK...")
        decompile(apk_path, decoded_dir)

        print("\n[2/7] Eliminando permisos invasivos...")
        manifest = decoded_dir / "AndroidManifest.xml"
        remove_invasive_permissions(manifest)

        print("\n[3/7] Ajustando Manifest para instalación...")
        fix_manifest_for_install(manifest)

        print("\n[4/7] Actualizando nombre de la aplicación...")
        strings_xml = decoded_dir / "res" / "values" / "strings.xml"
        change_app_name(strings_xml, args.name)

        print("\n[5/7] Recompilando con aapt2 --force-all...")
        rebuild(decoded_dir, unsigned_apk)

        print("\n[6/7] Alineando (zipalign -p 4)...")
        zipalign_apk(unsigned_apk, aligned_apk)

        print("\n[7/7] Firmando (v1 + v2 + v3)...")
        generate_keystore(keystore)
        sign_apk(aligned_apk, final_apk, keystore)

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
