import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client() {
    if (kReleaseMode) {
      final uri = Uri.tryParse(_configuredBaseUrl);
      if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
        throw const ApiException(
          'A versão release exige API_BASE_URL com um endereço HTTPS válido.',
        );
      }
    }
  }

  static const _configuredBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  final http.Client _client;
  final String _baseUrl = _configuredBaseUrl.replaceFirst(RegExp(r'/$'), '');
  void Function()? onUnauthorized;

  Future<String> login(String email, String password) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/login'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'senha': password}),
    );
    final payload = _decode(response);
    final token = payload['access_token'];
    if (token is! String || token.isEmpty) {
      throw const ApiException('A API não retornou um token de acesso.');
    }
    return token;
  }

  Future<List<Map<String, dynamic>>> getProperties(
    String token, {
    int pagina = 1,
    int tamanhoPagina = 10,
    String? busca,
    String statusLeilao = 'ativos',
    String ordenar = 'score',
    String? cidade,
    String? estado,
    String? tipo,
    double? valorMaximo,
    double? descontoMinimo,
  }) async {
    final query = <String, String>{
      'pagina': '$pagina',
      'tamanho_pagina': '$tamanhoPagina',
      'status_leilao': statusLeilao,
      'ordenar': ordenar,
      // Empty value disables the endpoint's default single-modality filter.
      'modalidade': '',
    };
    if (cidade != null && cidade.trim().isNotEmpty) {
      query['cidade'] = cidade.trim();
    }
    if (busca != null && busca.trim().isNotEmpty) {
      query['busca'] = busca.trim();
    }
    if (estado != null && estado.trim().isNotEmpty) {
      query['estado'] = estado.trim().toUpperCase();
    }
    if (tipo != null && tipo.trim().isNotEmpty) query['tipo'] = tipo.trim();
    if (valorMaximo != null) query['valor_maximo'] = '$valorMaximo';
    if (descontoMinimo != null) query['desconto_minimo'] = '$descontoMinimo';
    final response = await _client.get(
      Uri.parse('$_baseUrl/imoveis/').replace(queryParameters: query),
      headers: {'Authorization': 'Bearer $token'},
    );
    final payload = _decodeAuthenticated(response);
    final items = payload['items'];
    if (items is! List) {
      throw const ApiException(
          'A resposta da API não contém a lista de imóveis.');
    }
    return items.whereType<Map<String, dynamic>>().toList();
  }

  Future<Map<String, dynamic>> getProperty(String token, dynamic id) async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/imoveis/$id'),
      headers: {'Authorization': 'Bearer $token'},
    );
    return _decodeAuthenticated(response);
  }

  Future<Map<String, dynamic>> getCurrentUser(String token) async =>
      _requestMap(token, 'GET', '/usuarios/me');

  Future<List<Map<String, dynamic>>> getPropertyOpportunities(
          String token, dynamic propertyId) async =>
      _getList(token, '/oportunidades/imovel/$propertyId');

  Future<Map<String, dynamic>> createPropertyOpportunity(
          String token, int propertyId, int clientId) async =>
      _requestJsonMap(token, '/oportunidades', {
        'imovel_id': propertyId,
        'cliente_id': clientId,
      });

  Future<List<Map<String, dynamic>>> getProfitabilityScenarios(
          String token, int opportunityId) async =>
      _getList(token, '/oportunidades/$opportunityId/simulacoes');

  Future<Map<String, dynamic>> saveProfitabilityScenario(String token,
          int opportunityId, Map<String, dynamic> scenario) async =>
      _requestJsonMap(
          token, '/oportunidades/$opportunityId/simulacoes', scenario);

  Future<List<Map<String, dynamic>>> getAlerts(String token) =>
      _getList(token, '/alertas');

  Future<Map<String, dynamic>> saveAlert(
    String token,
    Map<String, dynamic> alert, {
    int? id,
  }) async {
    final response = id == null
        ? await _client.post(Uri.parse('$_baseUrl/alertas'),
            headers: _authJson(token), body: jsonEncode(alert))
        : await _client.put(Uri.parse('$_baseUrl/alertas/$id'),
            headers: _authJson(token), body: jsonEncode(alert));
    return _decodeAuthenticated(response);
  }

  Future<void> deleteAlert(String token, int id) async {
    final response = await _client.delete(Uri.parse('$_baseUrl/alertas/$id'),
        headers: {'Authorization': 'Bearer $token'});
    if (response.statusCode < 200 || response.statusCode >= 300) {
      _decodeAuthenticated(response);
    }
  }

  Future<List<Map<String, dynamic>>> getAlertScenarios(String token) =>
      _getList(token, '/alertas/cenarios');

  Future<List<Map<String, dynamic>>> getNotifications(String token) =>
      _getList(token, '/alertas/notificacoes');

  Future<Map<String, dynamic>> markNotificationRead(
          String token, int id) async =>
      _requestMap(token, 'POST', '/alertas/notificacoes/$id/lida');

  Future<List<Map<String, dynamic>>> _getList(String token, String path) async {
    final response = await _client.get(Uri.parse('$_baseUrl$path'),
        headers: {'Authorization': 'Bearer $token'});
    final decoded = _decodeAny(response, authenticated: true);
    if (decoded is! List) {
      throw const ApiException('A resposta da API não contém uma lista.');
    }
    return decoded.whereType<Map<String, dynamic>>().toList();
  }

  Future<Map<String, dynamic>> _requestMap(
      String token, String method, String path) async {
    final uri = Uri.parse('$_baseUrl$path');
    final headers = {'Authorization': 'Bearer $token'};
    final response = switch (method) {
      'POST' => await _client.post(uri, headers: headers),
      _ => await _client.get(uri, headers: headers),
    };
    return _decodeAuthenticated(response);
  }

  Future<Map<String, dynamic>> _requestJsonMap(
      String token, String path, Map<String, dynamic> body) async {
    final response = await _client.post(Uri.parse('$_baseUrl$path'),
        headers: _authJson(token), body: jsonEncode(body));
    return _decodeAuthenticated(response);
  }

  Map<String, String> _authJson(String token) => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

  Map<String, dynamic> _decodeAuthenticated(http.Response response) {
    final decoded = _decodeAny(response, authenticated: true);
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException('A API retornou uma resposta inválida.');
    }
    return decoded;
  }

  Object? _decodeAny(http.Response response, {bool authenticated = false}) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      if (authenticated && response.statusCode == 401) onUnauthorized?.call();
      final Object? errorPayload;
      try {
        errorPayload = jsonDecode(utf8.decode(response.bodyBytes));
      } on FormatException {
        throw ApiException('Erro HTTP ${response.statusCode}.');
      }
      final detail =
          errorPayload is Map<String, dynamic> ? errorPayload['detail'] : null;
      throw ApiException(
          detail is String ? detail : 'Erro HTTP ${response.statusCode}.');
    }
    final Object? decoded;
    try {
      decoded = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const ApiException('A API retornou uma resposta inválida.');
    }
    return decoded;
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded = _decodeAny(response);
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException('A API retornou uma resposta inválida.');
    }
    return decoded;
  }

  void close() => _client.close();
}

class ApiException implements Exception {
  const ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
