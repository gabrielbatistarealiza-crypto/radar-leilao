plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val releaseStoreFile = providers.environmentVariable("ANDROID_KEYSTORE_PATH")
val releaseStorePassword = providers.environmentVariable("ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = providers.environmentVariable("ANDROID_KEY_ALIAS")
val releaseKeyPassword = providers.environmentVariable("ANDROID_KEY_PASSWORD")
val hasReleaseSigning = listOf(
    releaseStoreFile,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { it.isPresent && it.get().isNotBlank() }

android {
    namespace = "com.radarleilao.radar_leilao"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    if (hasReleaseSigning) {
        signingConfigs.create("production") {
            storeFile = file(releaseStoreFile.get())
            storePassword = releaseStorePassword.get()
            keyAlias = releaseKeyAlias.get()
            keyPassword = releaseKeyPassword.get()
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.radarleilao.radar_leilao"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            if (hasReleaseSigning) {
                signingConfig = signingConfigs.getByName("production")
            }
        }
    }
}

val validateProductionRelease = tasks.register("validateProductionRelease") {
    group = "verification"
    description = "Checks production API and signing configuration before a release build."
    doLast {
        check(hasReleaseSigning) {
            "Release signing is not configured. Set ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS, and ANDROID_KEY_PASSWORD in the build environment."
        }
        check(file(releaseStoreFile.get()).isFile) {
            "ANDROID_KEYSTORE_PATH does not point to an existing keystore file."
        }
        val apiUrl = providers.environmentVariable("API_BASE_URL").orNull?.trim().orEmpty()
        check(apiUrl.startsWith("https://", ignoreCase = true) && apiUrl.length > "https://".length) {
            "Set API_BASE_URL in the build environment to the confirmed production HTTPS API URL and pass the same value with --dart-define=API_BASE_URL=... ."
        }
    }
}

tasks.configureEach {
    if (name.contains("Release", ignoreCase = true) && name != "validateProductionRelease") {
        dependsOn(validateProductionRelease)
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
