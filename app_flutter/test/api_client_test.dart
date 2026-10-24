import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:radar_leilao/src/api_client.dart';

void main() {
  test('401 em endpoint autenticado sinaliza sessão expirada', () async {
    var unauthorizedCalls = 0;
    final api = ApiClient(
      client: MockClient(
          (_) async => http.Response('{"detail":"Token inválido."}', 401)),
    );
    api.onUnauthorized = () {
      unauthorizedCalls++;
    };
    expect(api.onUnauthorized, isNotNull);
    addTearDown(api.close);

    await expectLater(
        api.getCurrentUser('token-expirado'), throwsA(isA<ApiException>()));
    expect(unauthorizedCalls, 1);
  });

  test('403 não encerra sessão e login inválido não encerra sessão existente',
      () async {
    var unauthorizedCalls = 0;
    final api = ApiClient(
      client: MockClient((request) async => request.url.path == '/login'
          ? http.Response('{"detail":"Credenciais inválidas."}', 401)
          : http.Response('{"detail":"Acesso negado."}', 403)),
    );
    api.onUnauthorized = () => unauthorizedCalls++;
    addTearDown(api.close);

    await expectLater(
        api.getCurrentUser('token-valido'), throwsA(isA<ApiException>()));
    await expectLater(
        api.login('a@exemplo.com', 'errada'), throwsA(isA<ApiException>()));
    expect(unauthorizedCalls, 0);
  });
}
