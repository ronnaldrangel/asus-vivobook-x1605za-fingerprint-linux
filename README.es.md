# Lector de huellas ASUS Vivobook 16 X1605ZA en Linux

**Driver en modo pulsación para ELAN7001 / 04F3:3212 / eFSA80SC con libfprint + SIGFM.**

[English](README.md) | [Español](README.es.md)

[![Linux](https://img.shields.io/badge/Linux-Ubuntu%2026.04-2b6cb0)](#compatibilidad)
[![License: LGPL-2.1-or-later](https://img.shields.io/badge/License-LGPL--2.1--or--later-blue.svg)](LICENSE)
[![Estado: funcionando](https://img.shields.io/badge/estado-funcionando-2f855a)](#resultados)

Este repositorio reúne un parche local de libfprint, un instalador reproducible
y notas de diagnóstico para el lector de huellas del **ASUS Vivobook 16
X1605ZA** (**ELAN7001**, HID **04F3:3212**, sensor **eFSA80SC 80×80**) en Linux.

En Windows el lector es de **pulsación**: apoyas el dedo en el botón de
encendido y desbloquea. El driver `elanspi` de Linux lo trata como **swipe**, por
eso aparecen errores como:

```text
No devices available
timed out waiting for image
swipe too short
No enough keypoints found
Cannot run while suspended
```

Este proyecto añade un camino **press** que captura una imagen completa de
80×80, usa SIGFM para comparar y expone el dispositivo como
`FP_SCAN_TYPE_PRESS`.

## Índice

- [¿Es para tu portátil?](#es-para-tu-portátil)
- [Síntomas](#síntomas)
- [Compatibilidad](#compatibilidad)
- [Instalación rápida](#instalación-rápida)
- [Registrar y verificar](#registrar-y-verificar)
- [Reintentos PAM opcionales](#reintentos-pam-opcionales)
- [Qué modifica el instalador](#qué-modifica-el-instalador)
- [Solución de problemas](#solución-de-problemas)
- [Notas técnicas](#notas-técnicas)
- [Privacidad](#privacidad)
- [Desinstalar](#desinstalar)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Créditos](#créditos)
- [Licencia](#licencia)

## ¿Es para tu portátil?

Ejecuta:

```bash
cat /sys/class/dmi/id/product_name
ls /sys/bus/spi/devices/ | grep -i ELAN
grep -i '^HID_ID' /sys/bus/hid/devices/*/uevent | grep -i 04F3
fprintd-list "$USER"
```

La huella de hardware esperada es:

```text
Vivobook_ASUSLaptop X1605ZA_X1605ZA
spi-ELAN7001:00
HID_ID=0018:000004F3:00003212
```

Si ves `No devices available` y esos identificadores, este repositorio apunta a
tu equipo. Si el PID o el modelo son distintos, el parche puede necesitar
ajustes.

## Síntomas

- `fprintd-list` responde `No devices available`.
- Configuración de GNOME no muestra la opción de huella.
- `fprintd-enroll` pasa una o dos etapas y luego dice
  `enroll-swipe-too-short`.
- El journal muestra `timed out waiting for image`.
- Tras un registro interrumpido aparece `Cannot run while suspended`.
- La verificación a veces registra `No enough keypoints found`.

El sensor suele estar bien; el problema es que se está usando la máquina de
estados de swipe en un sensor de área.

## Compatibilidad

| Elemento | Valor probado |
| --- | --- |
| Portátil | ASUS Vivobook 16 X1605ZA (`Vivobook_ASUSLaptop X1605ZA_X1605ZA`) |
| ACPI de huella | `ELAN7001` |
| PID HID/touchpad | `04F3:3212` |
| Sensor | `eFSA80SC`, 80×80 |
| Bus | SPI (`spi-ELAN7001:00`, `/dev/spidev0.0`) |
| Sistema | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| fprintd | 1.94.5 |
| Base libfprint | 1.95.1 + rama SIGFM |
| Escritorio | GNOME 50 / Wayland |

El parche está limitado a `ELAN7001` + `04F3:3212`. Otros sensores `eFSA80SC`
pueden necesitar otro PID y no están probados.

## Instalación rápida

Requisitos: Ubuntu/Debian con `apt`, `initramfs-tools`, sudo y reinicio.

```bash
git clone https://github.com/ronnaldrangel/asus-vivobook-x1605za-fingerprint-linux.git
cd asus-vivobook-x1605za-fingerprint-linux
sudo ./scripts/install.sh
sudo reboot
```

El instalador compila libfprint + SIGFM, lo instala en `/opt/elan3212` y hace
que solo fprintd cargue esa copia. No reemplaza el paquete de Ubuntu.

Después del reinicio:

```bash
cat /sys/module/spidev/parameters/bufsiz   # debe mostrar 32768
fprintd-list "$USER"
```

## Registrar y verificar

```bash
fprintd-enroll -f right-index-finger
```

Apoya el **dedo índice derecho** plano sobre el lector y mantenlo quieto 1–2
segundos. Repite **8 veces**, variando un poco la posición:

1. centro
2. ligeramente arriba
3. ligeramente abajo
4. ligeramente a la izquierda
5. ligeramente a la derecha
6. centro
7. ligeramente arriba
8. ligeramente abajo

Luego:

```bash
fprintd-verify right-index-finger
```

Para probar un dedo distinto, ejecuta lo mismo y usa otro dedo; debe responder
`verify-no-match`.

## Reintentos PAM opcionales

Ubuntu permite un intento de huella antes de pedir contraseña. Si la primera
captura sale con pocos keypoints, puedes activar tres intentos:

```bash
sudo ./scripts/install-pam-retries.sh
```

El script hace copia de `/etc/pam.d/common-auth`. La contraseña sigue disponible
como respaldo. No se instala por defecto.

## Qué modifica el instalador

- Compila libfprint desde `goodix-fp-linux-dev/libfprint` en el commit
  `07306bbc9256942595e31fb0f407b364ffa24d07`.
- Aplica `patches/0001-elan3212-press-mode.patch`.
- Instala la librería en `/opt/elan3212/lib`.
- Crea el drop-in de fprintd con `LD_LIBRARY_PATH=/opt/elan3212/lib`.
- Crea `/etc/modprobe.d/elanspi-fingerprint.conf` con
  `options spidev bufsiz=32768`.
- Añade `idma64` y `spidev` a `/etc/initramfs-tools/modules`.

No modifica PAM salvo que ejecutes el script opcional.

## Solución de problemas

| Síntoma | Qué revisar |
| --- | --- |
| `No devices available` | `ls /sys/bus/spi/devices/` debe mostrar `spi-ELAN7001:00`; la regla udev debe enlazarlo a `spidev`. |
| Sigue sin aparecer tras instalar | Comprueba que fprintd carga `/opt/elan3212/lib/libfprint-2.so.2.0.0` y que el drop-in está activo. |
| `timed out waiting for image` | Confirma `bufsiz=32768`; reinicia después de instalar. |
| `swipe too short` | El driver sigue en modo swipe; revisa `ELANSPI_PRESS_MODE` y `FP_SCAN_TYPE_PRESS`. |
| `No enough keypoints found` | Captura con pocas crestas. Apoya el dedo completo y reintenta; los reintentos PAM ayudan. |
| `Cannot run while suspended` | Reinicia fprintd tras una acción interrumpida: `sudo systemctl restart fprintd`. |
| `verify-no-match` inmediato | La plantilla puede estar mal; borra y registra de nuevo `right-index-finger`. |
| El registro termina demasiado rápido | Retira el dedo por completo entre las 8 pulsaciones. |
| Aserción `g_object_unref` | Conocida y no fatal en este build local; no impide registrar ni verificar. |

Diagnóstico:

```bash
journalctl -u fprintd -b --no-pager | tail -100
ls -l /dev/spidev0.0
cat /sys/module/spidev/parameters/bufsiz
fprintd-list "$USER"
```

## Notas técnicas

- El driver `elanspi` trata los sensores HV como swipe y limita el frame a 43
  filas.
- El camino press procesa la imagen completa de 80×80, corrige el fondo, rota
  90° a la derecha, normaliza el histograma y aplica un suavizado ligero.
- Espera 120 ms tras detectar el dedo, captura dos frames y envía el segundo.
- SIGFM se usa porque NBIS/Bozorth3 no discrimina bien en estas imágenes
  pequeñas de ELAN.
- `spidev.bufsiz=32768` evita que la transferencia de imagen se divida.
- El experimento 160×160 se descartó: era más lento y no mejoraba el matching.

El visor web de `tools/` es opcional. El volcado de imágenes está desactivado
por defecto; solo se activa con `ELANSPI_DEBUG_DUMP=1` en el drop-in.

## Privacidad

Este repositorio no contiene imágenes de huellas, plantillas ni datos
biométricos. Las herramientas de diagnóstico solo escriben capturas si se
activan explícitamente, y quedan en la máquina local. No publiques
`/var/lib/fprint` ni capturas de depuración.

## Desinstalar

```bash
sudo ./scripts/rollback.sh
sudo reboot
```

El rollback restaura PAM desde la copia si se usó el script opcional y devuelve
fprintd a la librería de Ubuntu. No borra automáticamente las huellas
registradas; puedes eliminarlas con:

```bash
fprintd-delete "$USER" -f right-index-finger
```

## Preguntas frecuentes

### ¿Por qué Windows desbloquea con un toque y Linux pide deslizar?

Windows usa el sensor de área en modo pulsación. El driver `elanspi` original lo
expone como swipe. Este parche añade el camino press.

### ¿Reemplaza el paquete libfprint de Ubuntu?

No. La librería parcheada queda aislada en `/opt/elan3212` y solo la carga
fprintd mediante un drop-in de systemd.

### ¿Funciona en otros Vivobook?

Está probado solo en X1605ZA con `ELAN7001` + `04F3:3212`. Otras variantes
`eFSA80SC` pueden necesitar otro PID y pruebas.

### ¿Por qué ocho muestras?

SIGFM guarda varias imágenes. Ocho pulsaciones con posiciones ligeramente
distintas toleran mejor la colocación del dedo que cinco.

### ¿Por qué no bajar el umbral SIGFM?

La mayoría de fallos son de captura (`No enough keypoints found`), no de
umbral. Bajar el umbral no arregla una imagen mala y podría aumentar falsos
positivos.

### ¿Funciona con sudo y la pantalla de inicio?

Sí, cuando fprintd detecta el dispositivo press. PAM ya está configurado en
Ubuntu; el script opcional solo aumenta los reintentos.

## Créditos

- [libfprint](https://gitlab.freedesktop.org/libfprint/libfprint) y la
  ingeniería inversa original de ELAN SPI de
  [mincrmatt12](https://github.com/mincrmatt12/elan-spi-fingerprint).
- [goodix-fp-linux-dev/libfprint](https://github.com/goodix-fp-linux-dev/libfprint)
  por la rama SIGFM.
- [r4nd3l/elan-3104-fingerprint-linux](https://github.com/r4nd3l/elan-3104-fingerprint-linux)
  por el trabajo de referencia eFSA80SC.
- [pesoiq/asus-expertbook-elan322d-fingerprint-linux](https://github.com/pesoiq/asus-expertbook-elan322d-fingerprint-linux)
  por la validación de captura y SIGFM en ELAN 322D.

## Licencia

Los cambios del driver y el parche se distribuyen bajo **GNU Lesser General
Public License, versión 2.1 o posterior**, igual que libfprint. Consulta
[LICENSE](LICENSE) y [NOTICE](NOTICE).
