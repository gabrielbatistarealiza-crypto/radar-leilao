import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:radar_leilao/src/api_client.dart';
import 'package:radar_leilao/src/radar_app.dart';

void main() {
  testWidgets('retorna ao login quando a API rejeita uma sessão expirada',
      (tester) async {
    // Sem sessão guardada: o _SessionGate restaura do armazenamento seguro
    // e só depois mostra o ecrã de login.
    FlutterSecureStorage.setMockInitialValues({});
    final api = ApiClient(
      client: MockClient((request) async {
        if (request.url.path == '/login') {
          return http.Response('{"access_token":"token-sintetico"}', 200);
        }
        if (request.url.path == '/usuarios/me') {
          return http.Response('{"id":42}', 200);
        }
        return http.Response('{"detail":"Token inválido."}', 401);
      }),
    );
    addTearDown(api.close);

    await tester.pumpWidget(RadarApp(api: api));
    // Espera a restauração da sessão terminar antes de procurar os campos.
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), 'teste@example.com');
    await tester.enterText(find.byType(TextField).at(1), 'senha');
    await tester.tap(find.widgetWithText(FilledButton, 'Entrar'));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Entrar'), findsOneWidget);
    expect(
        find.text(
            'Não foi possível conectar à API. Verifique o endereço e tente novamente.'),
        findsNothing);
  });
}
