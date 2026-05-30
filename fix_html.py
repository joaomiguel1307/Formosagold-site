with open('Formosagold.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'Saldo</button>',
    'Saldo</button>\n    <button class="tab" onclick="switchTab(\'transfer\')">Transferir</button>',
    1
)

panel = '\n  <div id="panel-transfer" class="panel"><div class="card"><div class="card-title">Transferir FMG</div><div class="input-group"><label>Chave Privada</label><input type="password" id="txPrivKey" placeholder="chave privada" /></div><div class="input-group"><label>Endereco Destino</label><input type="text" id="txTo" placeholder="endereco" /></div><div class="input-group"><label>Quantidade FMG</label><input type="number" id="txAmount" placeholder="10" /></div><button class="btn btn-gold" onclick="sendTransfer()" id="btnTransfer">Enviar FMG</button><div class="result" id="transferResult"></div></div></div>\n'

content = content.replace('<footer>', panel + '<footer>', 1)

js = '\nasync function sendTransfer(){const p=document.getElementById("txPrivKey").value.trim();const t=document.getElementById("txTo").value.trim();const a=parseInt(document.getElementById("txAmount").value);const r=document.getElementById("transferResult");r.classList.remove("show","success","error");if(!p||!t||!a){r.innerHTML="Preenche todos os campos.";r.classList.add("show","error");return;}const b=document.getElementById("btnTransfer");b.disabled=true;b.innerHTML="A enviar...";try{const res=await fetch("https://formosagold-site.onrender.com/transfer",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({private_key:p,to:t,amount:a})});const d=await res.json();if(d.result==="ok"){r.innerHTML="Enviado! "+a+" FMG. Minera para confirmar.";r.classList.add("show","success");document.getElementById("txPrivKey").value="";}else{r.innerHTML="Erro: "+d.result;r.classList.add("show","error");}}catch(e){r.innerHTML="Erro de ligacao.";r.classList.add("show","error");}finally{b.disabled=false;b.innerHTML="Enviar FMG";}}\n'

content = content.replace('// Init', js + '// Init', 1)

with open('Formosagold.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Feito!")
