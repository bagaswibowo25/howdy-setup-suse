# Howdy (login wajah ala Windows Hello) di openSUSE Leap 16.1

Catatan setup login wajah dengan kamera IR di laptop dual-boot (Windows + openSUSE),
supaya bisa diulang kalau install ulang / ada yang rusak setelah update.

Hasil akhir: `sudo`, lock screen KDE, dan login SDDM bisa dibuka dengan wajah,
emitter IR berkedip seperti di Windows Hello. SELinux tetap `enforcing`.

## Lingkungan

| Item | Nilai |
|---|---|
| OS | openSUSE Leap 16.1, kernel 6.12, KDE Plasma (sesi X11), SELinux enforcing |
| Kamera | Luxvisions `30c9:011a` "Integrated RGB Camera" (RGB + IR dalam satu modul USB) |
| Node RGB | `/dev/video0` (MJPG s/d 1080p) |
| Node IR | `/dev/video2` (GREY 640x360 / 360x360) |
| Path IR stabil | `/dev/v4l/by-path/pci-0000:00:14.0-usb-0:5:1.2-video-index0` |
| Howdy | 3.0.0 (commit `d3ab993`), build dari source + patch di repo ini |

## Inti masalah (baca ini dulu)

1. **Emitter IR tidak menyala sendiri di Linux.** Kamera ini memakai
   *Microsoft Camera Extension Unit* (MSXU, GUID `0f3f95dc-2632-4c4e-92c9-a04782f43bc8`),
   di kamera IR ada di **unit 7**. Kontrol **selector 6 = FACE_AUTHENTICATION**:
   - payload 9 byte, nilai default `[1, 3, 1, 0, ...]`
   - byte ke-2 = mode aktif: `1` = non-auth (emitter mati), `2` = auth dengan IR bergantian (Windows Hello)
   - **hanya bisa diubah saat kamera tidak streaming**, dan **kamera me-reset ke 1 setiap kali stream berhenti**.
2. Karena itu set sekali saat boot tidak cukup → Howdy di-patch supaya men-set mode 2
   tepat sebelum membuka kamera (`patches/howdy-ir-face-auth.patch`, aktif lewat `ir_face_auth = true`).
3. `linux-enable-ir-emitter` (6.1.2) **tidak** menemukan kontrol yang benar untuk kamera ini:
   - `unit 4 selector 2` dan `unit 4 selector 3` bikin kamera hang (harus shutdown penuh)
   - hasil akhirnya `unit 7 selector 9` → false positive, tidak berpengaruh
   - dia mencoba `7/6` tapi saat streaming, jadi tidak efektif.
   Tool ini **tidak diperlukan** untuk setup final.
4. **SDDM berjalan di domain SELinux `xdm_t`** yang dilarang `mmap` kamera → login SDDM gagal diam-diam
   (sudo & lock screen jalan karena unconfined). Butuh modul `selinux/howdy_sddm.cil`.

## Langkah setup dari nol

### 1. Dependensi (semua dari repo resmi Leap 16.1)

```bash
sudo zypper in -y v4l-utils meson ninja gcc-c++ pam-devel libinih-devel libevdev-devel \
  python313-devel python313-dlib python313-opencv python313-numpy git
```

### 2. Cek emitter bisa dinyalakan (opsional, untuk verifikasi hardware)

```bash
python3 tools/uvcxu.py /dev/video2            # dump nilai XU, cari baris "7 6 len 9"
python3 tools/ir_face_auth_test.py /dev/video2 2
```
Berhasil kalau `frame means` **bergantian terang/gelap**, mis. `[42, 6.6, 41, 6.6, ...]`,
dan lampu merah di samping lensa berkedip.

### 3. Build & install Howdy + patch

```bash
git clone https://github.com/boltgolt/howdy.git ~/src/howdy-ir/howdy
cd ~/src/howdy-ir/howdy
git checkout d3ab993                          # Howdy 3.0.0, patch dibuat di atas ini
git apply /path/ke/repo-ini/patches/howdy-ir-face-auth.patch

meson setup build --prefix=/usr --sysconfdir=/etc --libdir=lib64 \
  -Dpam_dir=/usr/lib64/security -Dpython_path=/usr/bin/python3
ninja -C build
sudo ninja -C build install
```

> **Jangan** pasang file dari tarball dengan `sudo tar -xzf ... -C /` — tar ikut menyalin
> owner dari arsip dan bisa mengubah owner `/`, `/etc`, `/usr` jadi bukan root.

### 4. Model wajah dlib

```bash
mkdir -p /tmp/dlib && cd /tmp/dlib
for f in dlib_face_recognition_resnet_model_v1 mmod_human_face_detector shape_predictor_5_face_landmarks; do
  curl -sL -o $f.dat.bz2 https://github.com/davisking/dlib-models/raw/master/$f.dat.bz2
done
bzip2 -d *.bz2
sudo install -o root -g root -m 644 *.dat /usr/share/dlib-data/
```

### 5. Konfigurasi Howdy

> `ninja install` **menimpa** `/etc/howdy/config.ini` — ulangi langkah ini setiap reinstall.

```bash
sudo sed -i \
  -e 's|^device_path = .*|device_path = /dev/v4l/by-path/pci-0000:00:14.0-usb-0:5:1.2-video-index0|' \
  -e 's|^frame_width = .*|frame_width = 640|' \
  -e 's|^frame_height = .*|frame_height = 360|' \
  /etc/howdy/config.ini
grep -q '^ir_face_auth' /etc/howdy/config.ini || \
  sudo sed -i '/^device_path = /a ir_face_auth = true' /etc/howdy/config.ini
```

Opsi tambahan dari patch (di section `[video]`, opsional):
- `ir_face_auth_unit` (default `7`)
- `ir_face_auth_mode` (default `2`)

### 6. Daftarkan & tes wajah

```bash
sudo howdy add
sudo env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY howdy test   # perlu env agar jendela preview bisa tampil
```

### 7. PAM

openSUSE menaruh file PAM bawaan di `/usr/lib/pam.d/`. Salin ke `/etc/pam.d/` (yang ini menang) lalu edit,
jadi file bawaan tidak tersentuh update.

**Selalu buka satu terminal `sudo -i` cadangan sebelum mengubah PAM.**

```bash
# sudo
sudo cp /usr/lib/pam.d/sudo /etc/pam.d/sudo
sudo sed -i '/^#%PAM-1.0/a auth     sufficient     pam_howdy.so' /etc/pam.d/sudo
sudo -k; sudo true            # harus "Identified face as ..."

# lock screen KDE (kcheckpass/kscreenlocker memakai service "kde")
sudo cp /usr/lib/pam.d/kde /etc/pam.d/kde
sudo sed -i '/^#%PAM-1.0/a auth     sufficient     pam_howdy.so' /etc/pam.d/kde

# login SDDM
sudo cp /usr/lib/pam.d/sddm /etc/pam.d/sddm
sudo sed -i '/pam_nologin.so/a auth     sufficient     pam_howdy.so' /etc/pam.d/sddm
```

Di SDDM / lock screen: klik kolom password, tekan **Enter dengan kolom kosong** untuk memulai scan.

Rollback: `sudo rm /etc/pam.d/{sudo,kde,sddm}` → kembali ke bawaan.

### 8. SELinux untuk SDDM

```bash
sudo semodule -i selinux/howdy_sddm.cil
```

Isinya hanya:
```
(allow xdm_t v4l_device_t (chr_file (map)))       ; SDDM boleh mmap kamera
(dontaudit xdm_t lib_t (dir (write add_name)))    ; diamkan log __pycache__ (harmless)
```
Hapus: `sudo semodule -r howdy_sddm`.

### 9. (Opsional) udev: matikan autosuspend kamera

Tidak wajib untuk setup final, tapi dipakai selama debugging:
```bash
sudo cp udev/99-ir-camera-no-autosuspend.rules /etc/udev/rules.d/
```

## Troubleshooting

| Gejala | Penyebab / solusi |
|---|---|
| `sudo howdy add` → "No face detected", lampu merah tidak kedip | `ir_face_auth = true` hilang dari config (mis. setelah `ninja install`) → ulangi langkah 5 |
| "Howdy could not find a camera device" | `device_path = none` setelah reinstall → langkah 5 |
| Lock screen & sudo bisa, login SDDM tidak | SELinux → `sudo grep -a denied /var/log/audit/audit.log \| tail`, tambahkan izin yang ditolak ke `howdy_sddm.cil`, `semodule -i` lagi |
| Penolakan SELinux tidak muncul di `journalctl` | Memang di `/var/log/audit/audit.log`, bukan journal |
| `howdy test` / tool GUI error "Could not load Qt platform plugin xcb" atau "Can't initialize GTK backend" | `sudo` tidak meneruskan display → `sudo env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY ...` |
| `sudo: linux-enable-ir-emitter: command not found` | `secure_path` sudo di openSUSE tidak mencakup `/usr/local/bin` → pakai path lengkap |
| Kamera hang / tidak bisa dibuka setelah eksperimen XU | **Shutdown penuh** (bukan restart), lalu coba lagi |
| Detektor HOG Howdy tidak menemukan wajah padahal wajah terlihat | Gambar terlalu gelap = emitter mati. Jangan naikkan `use_cnn` (CNN ~7.6 s/frame di CPU) — perbaiki emitternya |
| KWallet minta password setelah login wajah | Normal: wallet butuh password asli untuk dekripsi |

## Sisa dari proses debugging (boleh dibersihkan)

- `linux-enable-ir-emitter` 6.1.2 di `/usr/local` + service `linux-enable-ir-emitter.service` → tidak dipakai:
  ```bash
  sudo systemctl disable linux-enable-ir-emitter
  ```
  Config-nya ada di `/etc/linux-enable-ir-emitter/` (4/2 & 4/3 ditandai `disable`, 7/6 diubah manual ke `start` mode 2,
  tapi tetap tidak berguna karena kamera me-reset mode tiap stream berhenti).

## Isi repo

| Path | Isi |
|---|---|
| `patches/howdy-ir-face-auth.patch` | Patch Howdy: set MSXU FACE_AUTHENTICATION sebelum membuka kamera |
| `selinux/howdy_sddm.cil` | Modul SELinux untuk login SDDM |
| `udev/99-ir-camera-no-autosuspend.rules` | Matikan USB autosuspend kamera (opsional) |
| `tools/uvcxu.py` | Dump nilai kontrol UVC XU (read-only) |
| `tools/ir_face_auth_test.py` | Set mode FACE_AUTHENTICATION lalu ukur kecerahan frame (cek emitter) |
