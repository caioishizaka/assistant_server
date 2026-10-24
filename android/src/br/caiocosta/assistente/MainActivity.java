package br.caiocosta.assistente;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.SystemClock;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Locale;

/**
 * Ouve o comando, manda as hipóteses para o servidor e fala a resposta.
 *
 * Fase 7: a tela mostra todas as hipóteses com o CONFIDENCE_SCORES cru, para o teste da
 * confiança (PLAN.md, seção 10, Fase 7). Fica aberta depois de falar, até o botão "Fechar".
 */
public class MainActivity extends Activity implements RecognitionListener, TextToSpeech.OnInitListener {

    /** `adb logcat -s Assistente`: cada tentativa, com hipóteses, erro e envio. Nunca o token. */
    static final String TAG = "Assistente";
    private static final int PEDIDO_AUDIO = 1;
    private static final String UTTERANCE = "resposta";

    private TextView status;
    private TextView ouvido;
    private TextView resposta;
    private Button falar;

    private Config config;
    private SpeechRecognizer reconhecedor;
    private TextToSpeech tts;
    private boolean ttsPronto;
    private String falaPendente;
    private long inicioEscuta;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        config = new Config(this);
        setContentView(montarTela());
        tts = new TextToSpeech(this, this);
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            ouvir();
        } else {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, PEDIDO_AUDIO);
        }
    }

    @Override
    public void onRequestPermissionsResult(int codigo, String[] permissoes, int[] resultados) {
        super.onRequestPermissionsResult(codigo, permissoes, resultados);
        if (codigo == PEDIDO_AUDIO && resultados.length > 0 && resultados[0] == PackageManager.PERMISSION_GRANTED) {
            ouvir();
        } else {
            status.setText("Sem permissão de microfone");
        }
    }

    @Override
    protected void onDestroy() {
        if (reconhecedor != null) {
            reconhecedor.destroy();
        }
        if (tts != null) {
            tts.shutdown();
        }
        super.onDestroy();
    }

    private View montarTela() {
        LinearLayout tela = new LinearLayout(this);
        tela.setOrientation(LinearLayout.VERTICAL);
        tela.setPadding(48, 48, 48, 48);

        status = texto("");
        ouvido = texto("");
        resposta = texto("");
        tela.addView(status);
        tela.addView(ouvido);
        tela.addView(resposta);

        falar = new Button(this);
        falar.setText("Falar de novo");
        falar.setOnClickListener(v -> ouvir());
        tela.addView(falar);

        Button ajustes = new Button(this);
        ajustes.setText("Configurações");
        ajustes.setOnClickListener(v -> startActivity(new Intent(this, SettingsActivity.class)));
        tela.addView(ajustes);

        Button fechar = new Button(this);
        fechar.setText("Fechar");
        fechar.setOnClickListener(v -> finish());
        tela.addView(fechar);

        ScrollView rolagem = new ScrollView(this);
        rolagem.addView(tela);
        return rolagem;
    }

    private TextView texto(String inicial) {
        TextView t = new TextView(this);
        t.setText(inicial);
        t.setTextSize(18);
        t.setPadding(0, 24, 0, 24);
        return t;
    }

    /** Um reconhecedor novo a cada tentativa: reaproveitar o mesmo passa a dar "sem fala" na hora em
     *  vários aparelhos. O TTS para antes, para a resposta anterior não disputar o microfone. */
    private void ouvir() {
        if (tts != null) {
            tts.stop();
        }
        if (reconhecedor != null) {
            reconhecedor.destroy();
        }
        reconhecedor = SpeechRecognizer.createSpeechRecognizer(this);
        if (reconhecedor == null) {
            status.setText("Reconhecimento de voz indisponível neste aparelho");
            Log.w(TAG, "createSpeechRecognizer devolveu null");
            return;
        }
        reconhecedor.setRecognitionListener(this);
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5);
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
        status.setText("Ouvindo…");
        ouvido.setText("");
        resposta.setText("");
        falar.setEnabled(false);
        inicioEscuta = SystemClock.elapsedRealtime();
        Log.i(TAG, "ouvindo");
        reconhecedor.startListening(intent);
    }

    private long msDesdeInicio() {
        return SystemClock.elapsedRealtime() - inicioEscuta;
    }

    @Override
    public void onResults(Bundle resultados) {
        ArrayList<String> textos = resultados.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        float[] confianca = resultados.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES);
        Log.i(TAG, "resultado em " + msDesdeInicio() + " ms: hipoteses=" + textos
                + " confianca=" + Arrays.toString(confianca));
        mostrarOuvido(textos, confianca);
        JSONObject pedido = montarPedido(textos, confianca);
        if (pedido == null) {
            Log.w(TAG, "resultado sem hipótese com texto");
            mostrar("Não ouvi nada (resultado vazio, " + msDesdeInicio() + " ms)");
            return;
        }
        enviar(pedido);
    }

    /** Teste da confiança: o que o reconhecedor devolveu, sem tratamento. */
    private void mostrarOuvido(ArrayList<String> textos, float[] confianca) {
        StringBuilder linhas = new StringBuilder();
        linhas.append(confianca == null
                ? "CONFIDENCE_SCORES: ausente\n"
                : "CONFIDENCE_SCORES: " + confianca.length + " valores\n");
        if (textos != null) {
            for (int i = 0; i < textos.size(); i++) {
                linhas.append(i + 1).append(". ").append(textos.get(i))
                        .append("  [confiança: ")
                        .append(confianca != null && i < confianca.length ? String.valueOf(confianca[i]) : "—")
                        .append("]\n");
            }
        }
        ouvido.setText(linhas.toString());
    }

    /** Hipóteses em ordem; a confiança só entra quando é positiva (o Android manda -1 ou 0 para "sem"). */
    private static JSONObject montarPedido(ArrayList<String> textos, float[] confianca) {
        if (textos == null) {
            return null;
        }
        JSONArray hipoteses = new JSONArray();
        try {
            for (int i = 0; i < textos.size(); i++) {
                String texto = textos.get(i);
                if (texto == null || texto.trim().isEmpty()) {
                    continue;
                }
                JSONObject hipotese = new JSONObject();
                hipotese.put("text", texto);
                if (confianca != null && i < confianca.length && confianca[i] > 0) {
                    hipotese.put("confidence", confianca[i]);
                }
                hipoteses.put(hipotese);
            }
            if (hipoteses.length() == 0) {
                return null;
            }
            return new JSONObject().put("hypotheses", hipoteses);
        } catch (JSONException erro) {
            return null;
        }
    }

    private void enviar(JSONObject pedido) {
        status.setText("Falando com a casa…");
        new Thread(() -> {
            String fala;
            if (config.token().isEmpty()) {
                fala = "token não configurado";
                Log.w(TAG, "token não configurado: nada enviado ao servidor");
            } else {
                long inicio = SystemClock.elapsedRealtime();
                try {
                    Comando.Resposta r = Comando.enviar(config, pedido.toString());
                    fala = Comando.falaDa(r);
                    Log.i(TAG, "servidor respondeu " + r.status + " em "
                            + (SystemClock.elapsedRealtime() - inicio) + " ms: " + fala);
                } catch (Comando.SemConexao erro) {
                    fala = "sem conexão com a casa";
                    Log.w(TAG, "sem conexão (LAN e Meshnet): " + erro.getMessage());
                } catch (IOException erro) {
                    fala = "sem resposta da casa";
                    Log.w(TAG, "conectou mas não houve resposta: " + erro);
                }
            }
            String texto = fala;
            runOnUiThread(() -> terminar(texto));
        }).start();
    }

    private void terminar(String fala) {
        resposta.setText(fala);
        status.setText("Pronto");
        falar.setEnabled(true);
        falarTexto(fala);
    }

    private void mostrar(String mensagem) {
        status.setText(mensagem);
        falar.setEnabled(true);
    }

    private void falarTexto(String texto) {
        if (ttsPronto) {
            tts.speak(texto, TextToSpeech.QUEUE_FLUSH, null, UTTERANCE);
        } else {
            falaPendente = texto;
        }
    }

    @Override
    public void onInit(int estado) {
        if (estado != TextToSpeech.SUCCESS) {
            return;
        }
        int idioma = tts.setLanguage(Locale.forLanguageTag("pt-BR"));
        ttsPronto = idioma != TextToSpeech.LANG_MISSING_DATA && idioma != TextToSpeech.LANG_NOT_SUPPORTED;
        if (ttsPronto && falaPendente != null) {
            tts.speak(falaPendente, TextToSpeech.QUEUE_FLUSH, null, UTTERANCE);
            falaPendente = null;
        }
    }

    @Override
    public void onError(int erro) {
        long ms = msDesdeInicio();
        Log.w(TAG, "erro do reconhecedor " + erro + " após " + ms + " ms");
        String detalhe = " (erro " + erro + ", " + ms + " ms)";
        switch (erro) {
            case SpeechRecognizer.ERROR_NO_MATCH:
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                mostrar("Não ouvi nada" + detalhe);
                break;
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                mostrar("Sem permissão de microfone");
                break;
            default:
                mostrar("Erro no reconhecimento de voz" + detalhe);
                break;
        }
    }

    @Override
    public void onReadyForSpeech(Bundle parametros) {
    }

    @Override
    public void onBeginningOfSpeech() {
    }

    @Override
    public void onRmsChanged(float nivel) {
    }

    @Override
    public void onBufferReceived(byte[] buffer) {
    }

    @Override
    public void onEndOfSpeech() {
    }

    @Override
    public void onPartialResults(Bundle parciais) {
    }

    @Override
    public void onEvent(int tipo, Bundle parametros) {
    }
}
