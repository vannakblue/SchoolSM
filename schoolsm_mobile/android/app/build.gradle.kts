plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "kh.edu.schoolsm.schoolsm_mobile"
    compileSdk = 36
    buildToolsVersion = "36.0.0"
    ndkVersion = "28.2.13676358"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "kh.edu.schoolsm.schoolsm_mobile"
        minSdk = flutter.minSdkVersion
        targetSdk = 36
        multiDexEnabled = true
        versionCode = 1
        versionName = "1.0.0"
    }

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}
