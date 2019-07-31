var socket = null;

var utf8 = new TextEncoder('UTF-8');
var CLIENT_KEY = utf8.encode('Client Key');
var SERVER_KEY = utf8.encode('Server Key');


function b64encode(buf) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(buf)));
}

function b64decode(s) {
    // https://developer.mozilla.org/en-US/docs/Web/API/WindowBase64/Base64_encoding_and_decoding
    var bs = atob(s), buf = new Uint8Array(bs.length);
    Array.prototype.forEach.call(buf, function (el, idx, arr) { arr[idx] = bs.charCodeAt(idx); });
    return buf;
}

async function hmac_sha256(key, data) {
    var hmacKey = await crypto.subtle.importKey("raw", key, {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
    var hmac = await crypto.subtle.sign("HMAC", hmacKey, data);
    return new Uint8Array(hmac);
}

function xor(b1, b2) {
    var result = new Uint8Array(b1.length);
    for(var i = 0; i < b1.length; i++) {
        result[i] = b1[i] ^ b2[i];
    }
    return result;
}

async function decryptKey(mod, info, pwKey) {
    var keyBits = await window.crypto.subtle.deriveBits({name: "PBKDF2", salt: b64decode(info.key_spec.salt), iterations: info.key_spec.iterations, hash: "SHA-256"}, pwKey, 256);
    var aesKey = await window.crypto.subtle.importKey("raw", keyBits, "AES-GCM", false, ["decrypt"]);
    var privateBytes = await window.crypto.subtle.decrypt({name: "AES-GCM", iv: b64decode(info.nonce), tagLength: 128}, aesKey, b64decode(info.data));
    return mod.keyPair.fromSecretKey(new Uint8Array(privateBytes)).secretKey;
}

async function createChannelKey(name, password, serverKey) {
    var pwBytes = new TextEncoder('UTF-8').encode(password);
    var nameBytes = new TextEncoder('UTF-8').encode(name);
    var key = await window.crypto.subtle.importKey("raw", pwBytes, {name: "HKDF"}, false, ["deriveBits"]);
    var keyBits = await window.crypto.subtle.deriveBits({name: "HKDF", hash: "SHA-256", salt: serverKey, info: nameBytes}, key, 256);
    var keyHash = await window.crypto.subtle.digest("SHA-256", keyBits);
    var channelKey = await window.crypto.subtle.importKey("raw", keyBits, "AES-GCM", false, ["encrypt", "decrypt"]);
    return {
        key: channelKey,
        hash: keyHash
    };
}

async function encryptMessage(message, recipients, signingKey) {
    var plaintext = new TextEncoder('UTF-8').encode(message);
    var x25519keys = nacl.box.keyPair();
    var encrypted = {};
    for(var i = 0; i < recipients.length; i++) {
        var nonce = window.crypto.getRandomValues(new Uint8Array(12));
        var shared = nacl.scalarMult(x25519keys.secretKey, b64decode(recipients[i].x25519)); // is this backwards?
        var key = await window.crypto.subtle.importKey("raw", shared, {name: "HKDF"}, false, ["deriveBits"]);
        var keyBits = await window.crypto.subtle.deriveBits({name: "HKDF", hash: "SHA-256", salt: x25519keys.publicKey, info: nonce}, key, 256);
        var aesKey = await window.crypto.subtle.importKey("raw", keyBits, "AES-GCM", false, ["encrypt", "decrypt"]);
        var data = await window.crypto.subtle.encrypt({name: "AES-GCM", iv: nonce, tagLength: 128}, aesKey, plaintext);
        var signature = nacl.sign.detached(plaintext, signingKey);
        encrypted[recipients[i].ident] = {
            sender_key: b64encode(x25519keys.publicKey),
            nonce: b64encode(nonce),
            data: b64encode(data),
            signature: b64encode(signature)
        };
    }
    return encrypted;
}

async function decryptMessage(encrypted, x25519) {
    var senderKey = b64decode(encrypted.sender_key);
    var nonce = b64decode(encrypted.nonce);
    var shared = nacl.scalarMult(x25519, senderKey); // is this backwards?
    var key = await window.crypto.subtle.importKey("raw", shared, {name: "HKDF"}, false, ["deriveBits"]);
    var keyBits = await window.crypto.subtle.deriveBits({name: "HKDF", hash: "SHA-256", salt: senderKey, info: nonce}, key, 256);
    var aesKey = await window.crypto.subtle.importKey("raw", keyBits, "AES-GCM", false, ["encrypt", "decrypt"]);
    var text = await window.crypto.subtle.decrypt({name: "AES-GCM", iv: nonce, tagLength: 128}, aesKey, b64decode(encrypted.data));
    //if (nacl.sign.detached.verify(new Uint8Array(text), b64decode(encrypted.signature), b64decode(data.user.ed25519))) {
    return new TextDecoder('UTF-8').decode(text);
}

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
    vuetify: new Vuetify({
    }),
    data: {
        showNav: true,
        serverName: 'Neolith',
        serverKey: null,
        authenticated: false,
        showChannel: null,
        nickname: 'unnamed',
        username: 'guest',
        password: '',
        passwordKey: null,
        clientNonce: null,
        serverSignature: null,
        sessionId: null,
        chat: '',
        channels: [],
        channelUsers: {},
        channelKeys: {},
        users: [],
        buffer: {},
        showError: false,
        lastError: '',
        x25519: null,
        ed25519: null,
        ready: true,
        newChannel: {
            name: '',
            encrypted: false,
            private: false,
            key: ''
        },
        showNewChannel: false,
        joining: null,
        showJoin: false,
        channelPassword: ''
    },
    created: function() {
        this.$vuetify.theme.dark = true;
    },
    computed: {
        currentChannel: function() {
            return this.getChannel(this.showChannel);
        },
        currentBuffer: function() {
            return this.buffer[this.showChannel] || [];
        }
    },
    methods: {
        getChannel: function(name) {
            for(var i = 0; i < this.channels.length; i++) {
                if (this.channels[i].name == name) {
                    return this.channels[i];
                }
            }
            return null;
        },
        getUser: function(ident) {
            for(var i = 0; i < this.users.length; i++) {
                if (this.users[i].ident == ident) {
                    return this.users[i];
                }
            }
            return null;
        },
        login: function() {
            var self = this;
            var pwData = new TextEncoder('UTF-8').encode(this.password);
            window.crypto.subtle.importKey("raw", pwData, {name: "PBKDF2"}, false, ["deriveBits"]).then(function(pwKey) {
                self.passwordKey = pwKey;
                self.password = '';
                self.clientNonce = window.crypto.getRandomValues(new Uint8Array(16));
                socket = new WebSocket(window.location.protocol.replace('http', 'ws') + '//' + window.location.host + '/ws');
                socket.onmessage = function(event) {
                    self.handle(JSON.parse(event.data));
                };
                socket.onopen = function(event) {
                    self.write({
                        'challenge': {
                            'username': self.username,
                            'nonce': b64encode(self.clientNonce)
                        }
                    });
                };
                socket.onclose = function(event) {
                    self.cleanup();
                };
            });
        },
        cleanup: function() {
            socket = null;
            this.authenticated = false;
            this.showChannel = null;
            this.channels = [];
            this.users = [];
            this.buffer = {};
            this.channelUsers = {};
            this.channelKeys = {};
            this.showNewChannel = false;
            this.clientNonce = null;
            this.serverSignature = null;
            this.x25519 = null;
            this.ed25519 = null;
        },
        logout: function() {
            this.write({
                'logout': {}
            });
            socket.close(1000);
            this.cleanup();
        },
        write: function(tx) {
            console.log('SEND', tx);
            socket.send(JSON.stringify(tx));
        },
        handle: function(tx) {
            var self = this;
            console.log('RECV', tx);
            Object.getOwnPropertyNames(tx).forEach(function(ident) {
                if (ident == 'txid') {
                    // Not doing anything with transactions in this client (yet).
                }
                else if (ident == 'error') {
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
            if (this.joining in this.channelKeys) {
                delete this.channelKeys[this.joining];
                this.joining = null;
            }
            this.lastError = error;
            this.showError = true;
        },
        handlePacket: async function(ident, data) {
            var self = this;
            switch(ident) {
                case 'challenge.response':
                    // TODO: check that data.nonce starts with the this.clientNonce we sent
                    this.serverName = data.server_name;
                    // TODO: check password_spec.algorithm; assuming pbkdf2_sha256 for now.
                    var saltedPassword = await window.crypto.subtle.deriveBits({name: "PBKDF2", salt: b64decode(data.password_spec.salt), iterations: data.password_spec.iterations, hash: "SHA-256"}, this.passwordKey, 256);
                    var clientKey = await hmac_sha256(saltedPassword, CLIENT_KEY);
                    var serverKey = await hmac_sha256(saltedPassword, SERVER_KEY);
                    var storedKey = await window.crypto.subtle.digest("SHA-256", clientKey);
                    var clientSignature = await hmac_sha256(storedKey, b64decode(data.nonce));
                    var clientProof = xor(clientKey, clientSignature);
                    // We'll use this during login.response to verify the server
                    this.serverSignature = b64encode(await hmac_sha256(serverKey, b64decode(data.nonce)));
                    this.write({
                        'login': {
                            'nonce': data.nonce,
                            'proof': b64encode(clientProof),
                            'nickname': self.nickname
                        }
                    });
                    break;
                case 'login.response':
                    if (data.proof == this.serverSignature) {
                        this.sessionId = data.session_id;
                        this.serverKey = b64decode(data.server_key);
                        this.x25519 = await decryptKey(nacl.box, data.x25519, this.passwordKey);
                        this.ed25519 = await decryptKey(nacl.sign, data.ed25519, this.passwordKey);
                        this.authenticated = true;
                        this.write({
                            'user.list': {},
                            'channel.list': {}
                        });
                    }
                    else {
                        this.logout();
                        this.handleError('Server authentication failed.');
                    }
                    break;
                case 'user.listing':
                    this.users = data.users;
                    break;
                case 'channel.listing':
                    this.channels = data.channels;
                    break;
                case 'user.joined':
                    this.users.push(data.user);
                    break;
                case 'user.left':
                    var uid = data.user.ident;
                    var idx = this.users.findIndex(function(u) { return u.ident == uid; });
                    this.users.splice(idx, 1);
                    break;
                case 'channel.created':
                    this.channels.push(data.channel);
                    break;
                case 'channel.joined':
                    var user = this.getUser(data.user.ident);
                    if (user) {
                        this.channelUsers[data.channel].push(user);
                    }
                    this.joining = null;
                    break;
                case 'channel.left':
                    var uid = data.user.ident;
                    var idx = this.channelUsers[data.channel].findIndex(function(u) { return u.ident == uid; });
                    this.channelUsers[data.channel].splice(idx, 1);
                    break;
                case 'channel.userlist':
                    this.$set(this.channelUsers, data.channel, []);
                    data.users.forEach(function(u) {
                        var user = self.getUser(u.ident);
                        self.channelUsers[data.channel].push(user);
                    });
                    this.showChannel = data.channel;
                    break;
                case 'channel.posted':
                    var channel = this.getChannel(data.channel);
                    var user = this.getUser(data.user.ident);
                    if (channel && user) {
                        if (!(channel.name in this.buffer)) {
                            this.$set(this.buffer, channel.name, []);
                        }
                        if (channel.encrypted && data.encrypted) {
                            var chat = await decryptMessage(data.encrypted, this.x25519);
                            this.addChat(channel, chat, user, data.emote);
                            /*
                            var channelKey = this.channelKeys[channel.name].key;
                            var text = await window.crypto.subtle.decrypt({name: "AES-GCM", iv: b64decode(data.encrypted.nonce), tagLength: 128}, channelKey, b64decode(data.encrypted.data));
                            if (nacl.sign.detached.verify(new Uint8Array(text), b64decode(data.encrypted.signature), b64decode(data.user.ed25519))) {
                                var chat = new TextDecoder('UTF-8').decode(text);
                                this.addChat(channel, chat, user, data.emote);
                            }
                            else {
                                // TODO: show unsigned chat inline with some kind of marking
                                this.handleError('Could not verify message signature.');
                            }
                            */
                        }
                        else {
                            this.addChat(channel, data.chat, user, data.emote);
                        }
                    }
                    break;
                default:
                    console.log('unhandled packet', ident, data);
            }
        },
        addChat: function(channel, chat, user, emote) {
            var now = new Date();
            this.buffer[channel.name].push({
                timestamp: `${now.getHours()}:${now.getMinutes()}`,
                from: user.nickname,
                text: chat,
                emote: emote
            });
            this.$vuetify.goTo(9999);
        },
        join: function(name) {
            this.write({
                'channel.join': {
                    'channel': name
                }
            });
            /*
            var channel = this.getChannel(name);
            if (channel.encrypted) {
                var keyHash = null;
                this.joining = name;
                if (name in this.channelKeys) {
                    this.write({
                        'channel.join': {
                            'channel': name,
                            'key_hash': b64encode(this.channelKeys[name].hash)
                        }
                    });
                }
                else {
                    this.showJoin = true;
                }
            }
            else {
                this.write({
                    'channel.join': {
                        'channel': name
                    }
                });
            }
            */
        },
        createKeyAndJoin: async function() {
            this.channelKeys[this.joining] = await createChannelKey(this.joining, this.channelPassword, this.serverKey);
            this.join(this.joining);
            this.showJoin = false;
            this.channelPassword = '';
        },
        encryptChat: async function(chat, channelKey) {
            var chatBytes = new TextEncoder('UTF-8').encode(chat);
            var nonce = window.crypto.getRandomValues(new Uint8Array(12));
            var data = await window.crypto.subtle.encrypt({name: "AES-GCM", iv: nonce, tagLength: 128}, channelKey, chatBytes);
            var signature = nacl.sign.detached(chatBytes, this.ed25519);
            return {
                nonce: b64encode(nonce),
                data: b64encode(data),
                signature: b64encode(signature)
            };
        },
        post: async function() {
            var channel = this.currentChannel;
            if (channel.encrypted) {
                var context = utf8.encode(channel.name);
                this.write({
                    'channel.post': {
                        channel: channel.name,
                        //encrypted: await this.encryptChat(this.chat, this.channelKeys[channel].key),
                        encrypted: await encryptMessage(this.chat, this.channelUsers[channel.name], this.ed25519),
                        emote: false
                    }
                });
            }
            else {
                this.write({
                    'channel.post': {
                        channel: channel.name,
                        chat: this.chat,
                        emote: false
                    }
                });
            }
            this.chat = '';
        },
        createChannel: async function() {
            /*
            var keyHash = null;
            if (this.newChannel.encrypted) {
                var info = await createChannelKey(this.newChannel.name, this.newChannel.key, this.serverKey);
                // Would probably be better to do this after the channel is successfully created...
                this.channelKeys[this.newChannel.name] = info;
                keyHash = b64encode(info.hash);
            }
            */
            this.write({
                'channel.create': {
                    'channel': {
                        'name': this.newChannel.name,
                        'encrypted': this.newChannel.encrypted,
                        'private': this.newChannel.private
                    }
                }
            });
            this.showNewChannel = false;
        }
    }
});
