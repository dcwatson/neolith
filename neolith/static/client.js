var socket = null;

function b64encode(buf) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(buf)));
}

function b64decode(s) {
    // https://developer.mozilla.org/en-US/docs/Web/API/WindowBase64/Base64_encoding_and_decoding
    var bs = atob(s), buf = new Uint8Array(bs.length);
    Array.prototype.forEach.call(buf, function (el, idx, arr) { arr[idx] = bs.charCodeAt(idx); });
    return buf;
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
        showNewChannel: false
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
                socket = new WebSocket(window.location.protocol.replace('http', 'ws') + '//' + window.location.host + '/ws');
                socket.onmessage = function(event) {
                    self.handle(JSON.parse(event.data));
                };
                socket.onopen = function(event) {
                    self.write({
                        'challenge': {
                            'username': self.username
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
            this.showNewChannel = false;
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
            this.lastError = error;
            this.showError = true;
        },
        handlePacket: async function(ident, data) {
            var self = this;
            switch(ident) {
                case 'challenge.response':
                    this.serverName = data.server_name;
                    // TODO: check password_spec.algorithm; assuming pbkdf2_sha256 for now.
                    var pwHash = await window.crypto.subtle.deriveBits({name: "PBKDF2", salt: b64decode(data.password_spec.salt), iterations: data.password_spec.iterations, hash: "SHA-256"}, this.passwordKey, 256);
                    this.write({
                        'login': {
                            'password': b64encode(pwHash),
                            'nickname': self.nickname
                        }
                    });
                    break;
                case 'login.response':
                    this.sessionId = data.session_id;
                    this.serverKey = b64decode(data.server_key);
                    this.x25519 = await decryptKey(nacl.box, data.x25519, this.passwordKey);
                    this.ed25519 = await decryptKey(nacl.sign, data.ed25519, this.passwordKey);
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
            var keyHash = null;
            if (name in this.channelKeys) {
                keyHash = b64encode(this.channelKeys[name].hash);
            }
            // TODO: prompt for password if we don't already have it
            this.write({
                'channel.join': {
                    'channel': name,
                    'key_hash': keyHash
                }
            });
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
            var channel = this.showChannel;
            if (this.currentChannel.encrypted) {
                this.write({
                    'channel.post': {
                        channel: channel,
                        encrypted: await this.encryptChat(this.chat, this.channelKeys[channel].key),
                        emote: false
                    }
                });
            }
            else {
                this.write({
                    'channel.post': {
                        channel: channel,
                        chat: this.chat,
                        emote: false
                    }
                });
            }
            this.chat = '';
        },
        createChannel: async function() {
            var keyHash = null;
            if (this.newChannel.encrypted) {
                var info = await createChannelKey(this.newChannel.name, this.newChannel.key, this.serverKey);
                // Would probably be better to do this after the channel is successfully created...
                this.channelKeys[this.newChannel.name] = info;
                keyHash = b64encode(info.hash);
            }
            this.write({
                'channel.create': {
                    'channel': {
                        'name': this.newChannel.name,
                        'encrypted': this.newChannel.encrypted,
                        'private': this.newChannel.private
                    },
                    'key_hash': keyHash
                }
            });
            this.showNewChannel = false;
        }
    }
});
