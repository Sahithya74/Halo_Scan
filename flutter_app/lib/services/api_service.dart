/// Talks to the FastAPI backend (backend/app/main.py). One place for the base URL so
/// nothing is hard-coded across screens (spec section 33).
library;

import 'dart:convert';
import 'package:http/http.dart' as http;

import '../models/analysis_result.dart';

class ApiConfig {
  /// Android emulator -> host machine is 10.0.2.2; physical device needs the host's LAN IP.
  /// Override at build time with --dart-define=API_BASE_URL=http://192.168.x.x:8000
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiService {
  final http.Client _client;
  ApiService({http.Client? client}) : _client = client ?? http.Client();

  Future<AnalysisResult> analyze(List<int> imageBytes, String filename) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/analyze');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(http.MultipartFile.fromBytes('file', imageBytes, filename: filename));

    final streamedResponse = await _client.send(request);
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode != 200) {
      throw ApiException(response.body, statusCode: response.statusCode);
    }
    return AnalysisResult.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> qualityCheck(List<int> imageBytes, String filename) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/quality-check');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(http.MultipartFile.fromBytes('file', imageBytes, filename: filename));
    final streamedResponse = await _client.send(request);
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode != 200) {
      throw ApiException(response.body, statusCode: response.statusCode);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> history({int limit = 50}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/history?limit=$limit');
    final response = await _client.get(uri);
    if (response.statusCode != 200) {
      throw ApiException(response.body, statusCode: response.statusCode);
    }
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> health() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/health');
    final response = await _client.get(uri);
    if (response.statusCode != 200) {
      throw ApiException(response.body, statusCode: response.statusCode);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
