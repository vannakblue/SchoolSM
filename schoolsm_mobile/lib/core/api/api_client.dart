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
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
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
          error.type == DioExceptionType.receiveTimeout) {
        return "ការតភ្ជាប់ទៅកាន់ Server យឺតខ្លាំង (Connection Timeout)";
      }
      if (error.type == DioExceptionType.connectionError) {
        return "មិនអាចភ្ជាប់ទៅកាន់ Server បានទេ! សូមពិនិត្យអាសយដ្ឋាន Server ឬអ៊ីនធឺណិត។";
      }
      return "មានបញ្ហាបច្ចេកទេស (${error.response?.statusCode ?? 'Network Error'})";
    }
    return error.toString();
  }
}
