package br.caiocosta.assistente;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Manda o pedido para o servidor (PLAN.md, seção 8). Tenta primeiro o endereço da LAN, com
 * timeout de conexão curto; só falha de conexão passa para o da Meshnet. Resposta HTTP de erro
 * (4xx/5xx) nunca repete.
 */
final class Comando {

    static final int CONEXAO_LAN_MS = 800;
    static final int CONEXAO_MESH_MS = 3000;
    static final int LEITURA_MS = 6000;

    private Comando() {
    }

    static final class Resposta {
        final int status;
        final String corpo;

        Resposta(int status, String corpo) {
            this.status = status;
            this.corpo = corpo;
        }
    }

    /** Não conectou: o endereço não respondeu. Nada foi enviado, então dá para tentar outro. */
    static final class SemConexao extends IOException {
        SemConexao(String motivo) {
            super(motivo);
        }

        SemConexao(IOException causa) {
            super(causa.getMessage(), causa);
        }
    }

    static Resposta enviar(Config config, String json) throws IOException {
        String[] enderecos = {config.lan(), config.mesh()};
        int[] conexao = {CONEXAO_LAN_MS, CONEXAO_MESH_MS};
        SemConexao ultima = null;
        for (int i = 0; i < enderecos.length; i++) {
            if (enderecos[i].isEmpty()) {
                continue;
            }
            try {
                return postar(urlDoComando(enderecos[i]), conexao[i], config.token(), json);
            } catch (SemConexao erro) {
                ultima = erro;
            }
        }
        throw ultima != null ? ultima : new SemConexao("nenhum endereço configurado");
    }

    /** Fala para o usuário, a partir da resposta do servidor ou do código de erro HTTP. */
    static String falaDa(Resposta resposta) {
        if (resposta.status == 200) {
            try {
                return new JSONObject(resposta.corpo).getString("speech");
            } catch (JSONException erro) {
                return "resposta inválida do servidor";
            }
        }
        if (resposta.status == 401) {
            return "token recusado";
        }
        return "erro no servidor";
    }

    /** Endereço digitado sem esquema ("127.0.0.1:8197") vira http: o servidor é só HTTP. */
    /** O servidor entendeu e o hub aceitou (`status: ok`). É quando o app pode fechar sozinho. */
    static boolean deuCerto(Resposta resposta) {
        if (resposta.status != 200) {
            return false;
        }
        try {
            return "ok".equals(new JSONObject(resposta.corpo).optString("status"));
        } catch (JSONException erro) {
            return false;
        }
    }

    static String urlDoComando(String base) {
        String comEsquema = base.contains("://") ? base : "http://" + base;
        String semFim = comEsquema.endsWith("/") ? comEsquema : comEsquema + "/";
        return semFim + "v1/command";
    }

    private static Resposta postar(String url, int conexaoMs, String token, String json) throws IOException {
        HttpURLConnection con = (HttpURLConnection) new URL(url).openConnection();
        try {
            con.setConnectTimeout(conexaoMs);
            con.setReadTimeout(LEITURA_MS);
            con.setRequestMethod("POST");
            con.setDoOutput(true);
            con.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            con.setRequestProperty("Authorization", "Bearer " + token);
            try {
                con.connect();
            } catch (IOException erro) {
                throw new SemConexao(erro);
            }
            try (OutputStream saida = con.getOutputStream()) {
                saida.write(json.getBytes(StandardCharsets.UTF_8));
            }
            int status = con.getResponseCode();
            InputStream entrada = status >= 400 ? con.getErrorStream() : con.getInputStream();
            return new Resposta(status, entrada == null ? "" : ler(entrada));
        } finally {
            con.disconnect();
        }
    }

    private static String ler(InputStream entrada) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        int lidos;
        try (InputStream in = entrada) {
            while ((lidos = in.read(buffer)) != -1) {
                bytes.write(buffer, 0, lidos);
            }
        }
        return bytes.toString(StandardCharsets.UTF_8.name());
    }
}
