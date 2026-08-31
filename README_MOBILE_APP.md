# 📱 SchoolSM Cross-Platform Mobile App (Android & iOS)

កម្មវិធីទូរស័ព្ទដៃ **SchoolSM Mobile App** ត្រូវបានបង្កើតឡើងដោយប្រើប្រាស់ **Flutter Framework (Dart)** តភ្ជាប់ជាមួយ **Django REST API (JWT Authentication)** និង **Firebase Cloud Messaging (FCM)**។

---

## 🚀 របៀបបង្កើតឯកសារ APK ដោយចុច ១-Click (Build Android APK)

លោកអ្នកគ្រាន់តែ **Double-Click** លើឯកសារ៖
👉 **`build_android_apk.bat`** (ស្ថិតនៅ Folder ធំ `e:\SchoolSM\`)

ប្រព័ន្ធនឹងដំណើរការ៖
1. ទាញយក Packages ចាំបាច់ដោយស្វ័យប្រវត្តិ (`flutter pub get`)
2. បង្កើតឯកសារ Release APK (`flutter build apk --release`)
3. ចម្លងឯកសារចេញមកជា **`SchoolSM-Mobile.apk`** នៅ Folder ធំ
4. បើក Windows File Explorer ចង្អុលចំឯកសារ `.apk` ភ្លាមៗ ដើម្បីយកទៅដំឡើងលើទូរស័ព្ទដៃ Android!

---

## 🍏 របៀប Build សម្រាប់ iOS (iPhone / iPad)

ដើម្បី Build សម្រាប់ iOS តម្រូវឱ្យដំណើរការលើម៉ាស៊ីន macOS ដែលមាន Xcode៖
```bash
cd schoolsm_mobile
flutter build ipa --release
```
ឬបើក Folder `schoolsm_mobile/ios` នៅក្នុង **Xcode** ដើម្បីចុច Archive និង Upload ទៅកាន់ Apple App Store ឬ TestFlight។

---

## ⚙️ របៀបតភ្ជាប់ Firebase សម្រាប់ Push Notifications (FCM)

1. ចូលទៅកាន់ [Firebase Console](https://console.firebase.google.com/)
2. បង្កើតគម្រោង និងទាញយក៖
   - `google-services.json` ដាក់ក្នុងថត `schoolsm_mobile/android/app/`
   - `GoogleService-Info.plist` ដាក់ក្នុងថត `schoolsm_mobile/ios/Runner/`
   - Private Key Service Account JSON ដាក់ឈ្មោះថា **`firebase_credentials.json`** ក្នុងថត `e:\SchoolSM\`

---

## 🔑 គណនីសម្រាប់សាកល្បង Login លើ Mobile App

| តួនាទី (Role) | ឈ្មោះគណនី (Username / ID) | ពាក្យសម្ងាត់ (Password) |
| :--- | :--- | :--- |
| **Super Admin** | `admin` | `1627` |
| **គ្រូបង្រៀន (Teacher)** | លេខសម្គាល់គ្រូ (ឧ. `1670800407` / ID) | `p123456` |
| **សិស្ស (Student)** | លេខសម្គាល់សិស្ស (ឧ. `STU-2026-0013` / ID) | `p123456` |

---

## 🌐 ការកំណត់ Server URL លើ Mobile App
* លើផ្ទាំង Login ឬ Profile ចុចលើរូប **⚙️ Settings** ដើម្បីវាយបញ្ចូលអាសយដ្ឋាន Server (ឧ. `http://192.168.1.50:8000` ឬ `http://10.0.2.2:8000` សម្រាប់ Android Emulator ឬ Domain ផ្ទាល់ខ្លួន)។
