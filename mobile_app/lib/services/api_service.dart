import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import '../core/constants.dart';
import '../screens/error_screen.dart' show VerificationError;

/// Exception carrying the HTTP status code so the UI can route to the
/// correct error view (400 / 422 / 500 per API_CONTRACT.md).
class ApiException implements Exception {
  ApiException(this.error);

  final VerificationError error;

  @override
  String toString() => 'ApiException(${error.statusCode}): ${error.message}';
}

/// Service for communicating with the Dawae-Check backend.
class ApiService {
  const ApiService._();

  static final http.Client _client = http.Client();

  /// Check backend health.
  static Future<bool> healthCheck() async {
    try {
      final uri = Uri.parse('${ApiConstants.baseUrl}${ApiConstants.healthEndpoint}');
      final response = await _client.get(uri).timeout(const Duration(seconds: 10));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  /// Upload a packaging image for verification.
  ///
  /// Uses XFile/bytes so the same code works on Web, Android, and iOS.
  /// Returns the parsed JSON response on success, or throws an exception
  /// with a user-friendly message on failure.
  static Future<Map<String, dynamic>> verifyPackaging(
    XFile imageFile, {
    Uint8List? imageBytes,
    required String deviceId,
    required String facilityId,
    double? latitude,
    double? longitude,
  }) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}${ApiConstants.verifyEndpoint}');
    final request = http.MultipartRequest('POST', uri);

    request.fields['device_id'] = deviceId;
    request.fields['facility_id'] = facilityId;
    if (latitude != null) request.fields['latitude'] = latitude.toString();
    if (longitude != null) request.fields['longitude'] = longitude.toString();

    final bytes = imageBytes ?? await imageFile.readAsBytes();
    if (bytes.length > ApiConstants.maxImageSize) {
      throw Exception('Image is too large. Maximum size is 15 MB.');
    }

    final filename = imageFile.name.isNotEmpty
        ? imageFile.name
        : 'packaging_${DateTime.now().millisecondsSinceEpoch}.jpg';
    final multipartFile = http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: filename,
    );
    request.files.add(multipartFile);

    final streamedResponse = await request.send().timeout(const Duration(seconds: 60));
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }

    final message = _parseError(response);
    throw ApiException(
      VerificationError(statusCode: response.statusCode, message: message),
    );
  }

  static String _parseError(http.Response response) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      return body['detail']?.toString() ?? response.body;
    } catch (_) {
      return response.body;
    }
  }
}
