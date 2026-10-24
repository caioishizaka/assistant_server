package br.caiocosta.assistente;

import android.content.Context;
import android.content.SharedPreferences;

/** Endereços e token do servidor, guardados no aparelho (SharedPreferences). */
final class Config {

    static final String LAN_PADRAO = "http://192.168.68.86/assistant_server/";
    static final String MESH_PADRAO = "http://caio.ishizaka-andes.nord/assistant_server/";

    private static final String ARQUIVO = "assistente";
    private final SharedPreferences prefs;

    Config(Context contexto) {
        prefs = contexto.getSharedPreferences(ARQUIVO, Context.MODE_PRIVATE);
    }

    String lan() {
        return prefs.getString("lan", LAN_PADRAO);
    }

    String mesh() {
        return prefs.getString("mesh", MESH_PADRAO);
    }

    String token() {
        return prefs.getString("token", "");
    }

    void salvar(String lan, String mesh, String token) {
        prefs.edit()
                .putString("lan", lan.trim())
                .putString("mesh", mesh.trim())
                .putString("token", token.trim())
                .apply();
    }
}
