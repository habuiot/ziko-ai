# Házikó – NSPanel LAN diagnosztika

Egyszer futó, utána leálló HA app. Nem kér és nem olvas jelszót, nem futtat parancsot, nem ír fájlt, nem indít újra eszközt, nem nyit HTTP szolgáltatást és nem publikál portot.

Kizárólag a korábban a helyi Mosquitto által azonosított NSPanel Pro `192.168.10.207` címén a TCP 80/443/8080 portokat, valamint a HA szerver `192.168.10.118:1883` MQTT portját ellenőrzi. HTTP-n csak publikus GET / kérés történik, és csak HTTP státuszkódot és HTML oldal-címet naplóz, oldal tartalmát nem. Egyszeri mDNS-feloldási tesztet is végrehajt.

Az alkalmazás `startup: once`, `boot: manual_only`, védett és nincs tárolómappája. A futás után biztonságosan eltávolítható.
