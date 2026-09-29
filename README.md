# APK Cloner Pro (GitHub Action)

Clonador estático avanzado de APKs.

- Elimina permisos invasivos automáticamente
- Fuerza `extractNativeLibs="true"` y `testOnly="false"`
- Cambia el nombre visible de la app
- Recompila con **aapt2 --force-all**
- Alinea correctamente (`zipalign -p 4`)
- Firma con **v1 + v2 + v3**

## Uso rápido

1. Sube este repositorio a GitHub.
2. Ve a **Actions → Clone APK Pro → Run workflow**.
3. Rellena:
   - **apk_url**: URL directa del APK
   - **app_name**: Nuevo nombre visible
4. Descarga el Artifact `cloned-apk` cuando termine.

## Uso local

```bash
python3 cloner.py \
  --apk original.apk \
  --name "Mi App" \
  --output resultado.apk
```

## Notas importantes

- No se cambia el package name (evita ClassNotFoundException).
- Antes de instalar, **desinstala cualquier versión anterior** de la misma app.
- Si sigue fallando, captura el error real con:
  ```bash
  adb logcat | grep -E "PackageInstaller|INSTALL_FAILED"
  ```

## Licencia

MIT
