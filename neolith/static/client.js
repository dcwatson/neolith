var socket = null;
var algorithm = {
    name: "RSA-OAEP",
    hash: "SHA-256"
};
var config = {
    name: "RSA-OAEP",
    modulusLength: 4096,
    publicExponent: new Uint8Array([0x01, 0x00, 0x01]),
    hash: "SHA-256"
};

function b64encode(buf) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(buf)));
}

function b64decode(s) {
    // https://developer.mozilla.org/en-US/docs/Web/API/WindowBase64/Base64_encoding_and_decoding
    var bs = atob(s), buf = new Uint8Array(bs.length);
    Array.prototype.forEach.call(buf, function (el, idx, arr) { arr[idx] = bs.charCodeAt(idx); });
    return buf;
}

/*
function encrypt(keyData, str) {
    window.crypto.subtle.importKey("spki", keyData, algorithm, true, ['encrypt']).then(function(publicKey) {
        console.log(publicKey);
        var data = new TextEncoder('UTF-8').encode(str);
        window.crypto.subtle.encrypt(algorithm, publicKey, data).then(function(buf) {
            print(b64encode(buf));
        });
    });
}
*/

Vue.component('chat-line', {
    props: ['line'],
    template: `
        <div class="chat-line">
            <div class="timestamp">{{ line.timestamp }}</div>
            <div class="nickname">{{ line.from }}:</div>
            <div class="text">{{ line.text }}</div>
        </div>
    `
});

var vm = new Vue({
    el: '#app',
    data: {
        showNav: true,
        serverName: 'Neolith',
        authenticated: false,
        showChannel: 'public',
        nickname: 'unnamed',
        username: 'guest',
        password: '',
        chat: '',
        channels: [],
        users: [],
        buffer: {},
        showError: false,
        lastError: '',
        privateKey: null,
        publicKey: null,
        ready: false
    },
    computed: {
        currentChannel: function() {
            var show = this.showChannel;
            return this.channels.find(function(c) { return c.name == show; });
        },
        currentBuffer: function() {
            return this.buffer[this.showChannel] || [];
        }
    },
    created: function() {
        var self = this;
        window.crypto.subtle.generateKey(config, false, ["encrypt", "decrypt"]).then(function(keyPair) {
            self.privateKey = keyPair.privateKey;
            self.publicKey = keyPair.publicKey;
            self.ready = true;
        });
    },
    methods: {
        decrypt: function(buf) {
        },
        login: function() {
            var self = this;
            socket = new WebSocket('ws://' + window.location.host + '/ws');
            socket.onmessage = function(event) {
                self.handle(JSON.parse(event.data));
            };
            socket.onopen = function(event) {
                window.crypto.subtle.exportKey("spki", self.publicKey).then(function(pubkey) {
                    self.write({
                        'login': {
                            'nickname': self.nickname,
                            'username': self.username,
                            'password': self.password,
                            'pubkey': b64encode(pubkey)
                        }
                    });
                    self.password = '';
                });
            };
        },
        logout: function() {
            this.write({
                'logout': {}
            });
            socket.close(1000);
            socket = null;
            this.authenticated = false;
            this.channels = [];
            this.users = [];
            this.buffer = {};
        },
        write: function(tx) {
            console.log('SEND', tx);
            socket.send(JSON.stringify(tx));
        },
        handle: function(tx) {
            var self = this;
            console.log('RECV', tx);
            Object.getOwnPropertyNames(tx).forEach(function(ident) {
                if(ident == 'txid') {
                    // Not doing anything with transactions in this client (yet).
                }
                else if(ident == 'error') {
                    self.handleError(tx[ident]);
                }
                else {
                    tx[ident].forEach(function(data) {
                        self.handlePacket(ident, data);
                    });
                }
            });
        },
        handleError: function(error) {
            this.lastError = error;
            this.showError = true;
        },
        handlePacket: function(ident, data) {
            switch(ident) {
                case 'login.response':
                    this.serverName = data.server_name;
                    this.authenticated = true;
                    this.write({
                        'user.list': {},
                        'channel.list': {}
                    });
                    break;
                case 'user.listing':
                    this.users = data.users;
                    break;
                case 'channel.listing':
                    this.channels = data.channels;
                    this.write({
                        'channel.join': {
                            'channel': 'public'
                        }
                    });
                    break;
                case 'user.joined':
                    this.users.push(data.user);
                    break;
                case 'user.left':
                    var uid = data.user.ident;
                    var idx = this.users.findIndex(function(u) { return u.ident == uid; });
                    this.users.splice(idx, 1);
                    break;
                case 'channel.posted':
                    if (!(data.channel in this.buffer)) {
                        this.$set(this.buffer, data.channel, []);
                    }
                    /*
                        var buf = b64decode(data.encrypted);
                        window.crypto.subtle.decrypt(algorithm, this.privateKey, buf).then(function(plaintext) {
                            var str = new TextDecoder('UTF-8').decode(plaintext);
                            console.log(str);
                        });
                    */
                    var now = new Date();
                    this.buffer[data.channel].push({
                        timestamp: `${now.getHours()}:${now.getMinutes()}`,
                        from: data.user.nickname,
                        text: data.chat,
                        emote: data.emote
                    });
                    break;
                default:
                    console.log('unhandled packet', ident, data);
            }
        },
        post: function() {
            this.write({
                'channel.post': {
                    channel: this.showChannel,
                    chat: this.chat,
                    emote: false
                }
            });
            this.chat = '';
        }
    }
});
