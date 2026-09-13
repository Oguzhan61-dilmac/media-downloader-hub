# 🚀 Google Play Store (AAB & Keystore) Yayınlama Kılavuzu

Bu doküman, **Media Downloader Hub** mobil uygulamasının Google Play Console ortamına **Android App Bundle (.aab)** formatında imzalanarak yüklenmesi için gerekli tüm adımları içerir.

---

## 📋 1. Ön Gereksinimler & Paket Doğrulaması

Play Store standartlarına göre uygulamanın paket kimliği ve sürüm kodları doğrulanmıştır:

- **Paket Adı (Application ID)**: `com.mediadownloader.hub.mobile` (`mobile/android/app/build.gradle.kts`)
- **Sürüm Adı (Version Name)**: `1.0.0` (`mobile/pubspec.yaml -> version: 1.0.0+1`)
- **Sürüm Kodu (Version Code)**: `1` (`+1` ifadesi)

---

## 🔑 2. Release Keystore İletişim Anahtarı Oluşturma

Google Play Store'a yüklenecek `.aab` veya `.apk` paketlerinin dijital olarak imzalanması zorunludur.

Terminalde (veya Komut İstemcisinde) `keytool` kullanarak bir `upload-keystore.jks` dosyası oluşturun:

```bash
keytool -genkey -v -keystore upload-keystore.jks -storetype JKS -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

> **Önemli**: Oluşturulan `upload-keystore.jks` dosyasını `mobile/android/app/upload-keystore.jks` konumuna koyun ve **ASLA git deposuna eklemeyin** (`.gitignore` içerisinde gizlenmelidir).

---

## ⚙️ 3. Gradle İmzalamasını Yapılandırma

### Adım A: `android/key.properties` Dosyası Oluşturun
`mobile/android/key.properties` adında bir dosya açın ve keystore bilgilerinizi ekleyin:

```properties
storePassword=KEYSTORE_SIFRENIZ
keyPassword=ANAHTAR_SIFRENIZ
keyAlias=upload
storeFile=upload-keystore.jks
```

### Adım B: `android/app/build.gradle.kts` Güncellemesi
`build.gradle.kts` içerisindeki `android` bloğunu aşağıdaki gibi yapılandırın:

```kotlin
import java.io.FileInputStream
import java.util.Properties

val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    ...
    signingConfigs {
        create("release") {
            keyAlias = keystoreProperties["keyAlias"] as String?
            keyPassword = keystoreProperties["keyPassword"] as String?
            storeFile = keystoreProperties["storeFile"]?.let { file(it) }
            storePassword = keystoreProperties["storePassword"] as String?
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
```

---

## 📦 4. Play Store İmzalı AAB (Android App Bundle) Derleme

Google Play Console yalnızca `.aab` formatında paket kabul etmektedir.

`mobile/` dizininde aşağıdaki komut ile üretim paketini derleyin:

```bash
cd mobile

# Google Play Store üretim paketi (.aab)
flutter build appbundle --release
```

Derleme tamamlandığında dosyanız burada hazır olacaktır:
`mobile/build/app/outputs/bundle/release/app-release.aab`

---

## 📤 5. Google Play Console Yükleme Adımları

1. [Google Play Console](https://play.google.com/console) panosuna giriş yapın.
2. **Uygulama Oluştur** butonuna basarak `Media Downloader Hub` ismini verin.
3. **Üretim (Production)** veya **Kapalı Test (Closed Testing)** sekmesine gidin.
4. Oluşturulan `app-release.aab` dosyasını sürüm yükleme alanına sürükleyin.
5. Gizlilik Politikası (Privacy Policy) URL'sini ve içerik derecelendirme anketini tamamlayıp incelemeye gönderin.
