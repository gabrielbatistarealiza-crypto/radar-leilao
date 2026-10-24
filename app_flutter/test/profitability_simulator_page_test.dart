import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:radar_leilao/src/api_client.dart';
import 'package:radar_leilao/src/profitability_simulator_page.dart';

void main() {
  testWidgets('explica o efeito do primeiro salvamento', (tester) async {
    final client = MockClient((request) async => http.Response('[]', 200));
    final api = ApiClient(client: client);
    addTearDown(api.close);

    await tester.pumpWidget(MaterialApp(
      home: ProfitabilitySimulatorPage(
        api: api,
        token: 'token-sintetico',
        property: const {'id': 1, 'titulo': 'Imóvel de teste'},
      ),
    ));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Ao salvar seu primeiro cenário, será criada uma oportunidade na sua conta e seu interesse por este imóvel será registrado.',
      ),
      findsOneWidget,
    );
  });
}
