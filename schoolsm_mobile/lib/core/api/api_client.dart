import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  late Dio dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  ApiClient._internal() {
    dio = Dio(
      BaseOptions(
        connectTimeout: const Duration(seconds: 60),
        receiveTimeout: const Duration(seconds: 60),
        sendTimeout: const Duration(seconds: 60),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    // Add Auth Token Interceptor
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) {
          return handler.next(e);
        },
      ),
    );
  }

  static String getErrorMessage(dynamic error) {
    if (error is DioException) {
      if (error.response?.data != null && error.response?.data is Map) {
        final data = error.response!.data as Map;
        if (data.containsKey('message')) {
          return data['message'].toString();
        }
        if (data.containsKey('detail')) {
          return data['detail'].toString();
        }
      }
      if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout ||
          error.type == DioExceptionType.sendTimeout) {
        return "ការតភ្ជាប់ទៅកាន់ Server យឺត (Connection Timeout)! ប្រសិនបើ Server កំពុងភ្ញាក់ (Cold Start) សូមរង់ចាំបន្តិច រួចព្យាយាមម្តងទៀត។";
      }
      if (error.type == DioExceptionType.connectionError) {
        return "មិនអាចភ្ជាប់ទៅកាន់ Server បានទេ! ប្រសិនបើ Server នៅ Sleep Mode សូមរង់ចាំប្រហែល 30 វិនាទីដើម្បីឱ្យ Server ភ្ញាក់ រួចព្យាយាមម្តងទៀត។";
      }
      return "មានបញ្ហាបច្ចេកទេស (${error.response?.statusCode ?? 'Network Error'})";
    }
    return error.toString();
  }
}
