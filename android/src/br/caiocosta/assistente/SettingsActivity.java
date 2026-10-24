package br.caiocosta.assistente;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Endereços da LAN e da Meshnet, e o token do servidor. Nada além disso. */
public class SettingsActivity extends Activity {

    private EditText lan;
    private EditText mesh;
    private EditText token;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        Config config = new Config(this);

        LinearLayout tela = new LinearLayout(this);
        tela.setOrientation(LinearLayout.VERTICAL);
        tela.setPadding(48, 48, 48, 48);

        lan = campo(tela, "Endereço da LAN", config.lan(), false);
        mesh = campo(tela, "Endereço da Meshnet", config.mesh(), false);
        token = campo(tela, "Token", config.token(), true);

        Button salvar = new Button(this);
        salvar.setText("Salvar");
        salvar.setOnClickListener(v -> {
            config.salvar(lan.getText().toString(), mesh.getText().toString(), token.getText().toString());
            finish();
        });
        tela.addView(salvar);

        ScrollView rolagem = new ScrollView(this);
        rolagem.addView(tela);
        setContentView(rolagem);
    }

    private EditText campo(LinearLayout tela, String rotulo, String valor, boolean secreto) {
        TextView titulo = new TextView(this);
        titulo.setText(rotulo);
        titulo.setTextSize(16);
        tela.addView(titulo);

        EditText campo = new EditText(this);
        campo.setText(valor);
        campo.setSingleLine(true);
        if (secreto) {
            campo.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        }
        tela.addView(campo);
        return campo;
    }
}
