# APK Cloner Pro (GitHub Action)

Clonador estático avanzado de APKs. Descompila, elimina permisos invasivos, cambia package name y nombre visible, recompila y firma automáticamente.

## Características

- Eliminación automática de permisos sensibles (ubicación, teléfono, contactos, SMS, cámara, etc.)
- Cambio de package name y app name
- Firma con keystore de depuración generado al vuelo
- Ejecución 100% en GitHub Actions

## Uso rápido

1. Sube este repositorio a GitHub.
2. Ve a **Actions → Clone APK Pro → Run workflow**.
3. Rellena:
   - **apk_url**: URL directa del APK
   - **app_name**: Nuevo nombre visible
   - **package_name**: Nuevo package (ej: `com.miempresa.clon`)
4. Descarga el Artifact `cloned-apk` cuando termine.

## Uso local

```bash
python3 cloner.py \
  --apk original.apk \
  --name "Mi App" \
  --package com.ejemplo.clon \
  --output resultado.apk
```

## Licencia

MIT
