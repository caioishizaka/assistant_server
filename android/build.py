"""Constrói o APK do assistente sem Gradle, com as ferramentas do Android SDK (Linux).

    ANDROID_HOME=~/android-sdk python3 android/build.py           gera android/build/assistente.apk
    ANDROID_HOME=~/android-sdk python3 android/build.py install   gera e instala (adb install -r)

Molde: ~/dev/home_devices/android/build.py (Windows). Aqui: caminhos e nomes de Linux, e
`javac --release 17` (o JDK 21 do andes gera bytecode 21 com `-source/-target 17`).
A saída fica em android/build/, ignorada pelo git.
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VERSION_CODE = 1
VERSION_NAME = "1.0"
MIN_SDK = 30  # Android 11: o <queries> do manifesto depende disso
TARGET_SDK = 36

HERE = Path(__file__).resolve().parent
OUT = HERE / "build"
KEYSTORE = Path.home() / ".android" / "debug.keystore"


def sdk_root() -> Path:
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(var):
            return Path(os.environ[var])
    sys.exit("defina ANDROID_HOME apontando para o Android SDK (ex.: ~/android-sdk)")


def newest(folder: Path) -> Path:
    """Subpasta de versão mais alta (build-tools/36.1.0, platforms/android-36)."""
    def chave(p: Path):
        return tuple(int(n) for n in re.findall(r"\d+", p.name))
    return max((p for p in folder.iterdir() if p.is_dir()), key=chave)


def run(args) -> None:
    subprocess.run([str(a) for a in args], check=True)


def ensure_keystore() -> None:
    if KEYSTORE.exists():
        return
    KEYSTORE.parent.mkdir(parents=True, exist_ok=True)
    run(["keytool", "-genkeypair", "-keystore", KEYSTORE,
         "-storepass", "android", "-keypass", "android",
         "-alias", "androiddebugkey", "-keyalg", "RSA", "-keysize", "2048",
         "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US"])


def build() -> Path:
    sdk = sdk_root()
    bt = newest(sdk / "build-tools")
    aapt2, d8, zipalign, apksigner = bt / "aapt2", bt / "d8", bt / "zipalign", bt / "apksigner"
    jar = newest(sdk / "platforms") / "android.jar"

    work = OUT / "work"
    shutil.rmtree(work, ignore_errors=True)
    gen, classes, dex = work / "gen", work / "classes", work / "dex"
    for pasta in (gen, classes, dex):
        pasta.mkdir(parents=True)

    # 1-2: recursos e R.java
    run([aapt2, "compile", "--dir", HERE / "res", "-o", work / "res.zip"])
    run([aapt2, "link", "-I", jar,
         "--manifest", HERE / "AndroidManifest.xml",
         "--java", gen,
         "--min-sdk-version", MIN_SDK, "--target-sdk-version", TARGET_SDK,
         "--version-code", VERSION_CODE, "--version-name", VERSION_NAME,
         "-o", work / "base.apk", work / "res.zip"])

    # 3-4: Java -> classes -> dex
    fontes = list((HERE / "src").rglob("*.java")) + list(gen.rglob("R.java"))
    run(["javac", "--release", "17", "-encoding", "UTF-8", "-Xlint:-options",
         "-cp", jar, "-d", classes, *fontes])
    run([d8, "--lib", jar, "--min-api", MIN_SDK, "--output", dex,
         *classes.rglob("*.class")])

    # 5: dex dentro do apk
    base = work / "base.apk"
    with zipfile.ZipFile(base, "a") as z:
        z.write(dex / "classes.dex", "classes.dex", compress_type=zipfile.ZIP_DEFLATED)

    # 6-7: alinhar e assinar com a chave de debug
    alinhado = work / "aligned.apk"
    run([zipalign, "-f", "-p", "4", base, alinhado])
    ensure_keystore()
    apk = OUT / "assistente.apk"
    run([apksigner, "sign", "--ks", KEYSTORE, "--ks-key-alias", "androiddebugkey",
         "--ks-pass", "pass:android", "--key-pass", "pass:android",
         "--out", apk, alinhado])
    run([apksigner, "verify", apk])
    print(f"APK pronto: {apk}")
    return apk


if __name__ == "__main__":
    apk_pronto = build()
    if "install" in sys.argv[1:]:
        run([sdk_root() / "platform-tools" / "adb", "install", "-r", apk_pronto])
