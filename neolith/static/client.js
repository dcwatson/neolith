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
        showChannel: null,
        nickname: 'unnamed',
        username: 'guest',
        password: '',
        sessionId: null,
        chat: '',
        channels: [],
        channelUsers: {},
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
            return this.getChannel(this.showChannel);
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
            this.channelUsers = {};
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
        handlePacket: function(ident, data) {
            switch(ident) {
                case 'login.response':
                    this.serverName = data.server_name;
                    this.sessionId = data.session_id;
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
                case 'channel.joined':
                    var channel = this.getChannel(data.channel);
                    if (data.user.ident == this.sessionId) {
                        // This was us joining a channel, request the userlist for it.
                        this.write({
                            'channel.users': {
                                'channel': data.channel
                            }
                        });
                        this.showChannel = data.channel;
                    }
                    else {
                        if (!(data.channel in this.channelUsers)) {
                            this.$set(this.channelUsers, data.channel, []);
                        }
                        var user = this.getUser(data.user.ident);
                        if (user) {
                            this.channelUsers[data.channel].push(user);
                        }
                    }
                    break;
                case 'channel.left':
                    var uid = data.user.ident;
                    var idx = this.channelUsers[data.channel].findIndex(function(u) { return u.ident == uid; });
                    this.channelUsers[data.channel].splice(idx, 1);
                    break;
                case 'channel.userlist':
                    if (!(data.channel in this.channelUsers)) {
                        this.$set(this.channelUsers, data.channel, []);
                    }
                    var self = this;
                    data.users.forEach(function(u) {
                        var user = self.getUser(u.ident);
                        self.channelUsers[data.channel].push(user);
                    });
                    break;
                case 'channel.posted':
                    var channel = this.getChannel(data.channel);
                    var user = this.getUser(data.user.ident);
                    var self = this;
                    if (channel && user) {
                        if (!(channel.name in this.buffer)) {
                            this.$set(this.buffer, channel.name, []);
                        }
                        if (channel.encrypted && data.encrypted) {
                            window.crypto.subtle.decrypt(algorithm, this.privateKey, b64decode(data.encrypted)).then(function(plaintext) {
                                var chat = new TextDecoder('UTF-8').decode(plaintext);
                                self.addChat(channel, chat, user, data.emote);
                            });
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
        },
        post: function() {
            var self = this;
            var channel = this.showChannel;
            if (this.currentChannel.encrypted) {
                var data = new TextEncoder('UTF-8').encode(this.chat);
                var promises = [];
                this.channelUsers[channel].forEach(function(u) {
                    if (u.pubkey) {
                        // TODO: cache imported public keys? message signing??
                        promises.push(window.crypto.subtle.importKey("spki", b64decode(u.pubkey), algorithm, true, ['encrypt']).then(function(publicKey) {
                            return window.crypto.subtle.encrypt(algorithm, publicKey, data).then(function(buf) {
                                return {
                                    session_id: u.ident,
                                    data: b64encode(buf)
                                };
                            });
                        }));
                    }
                });
                Promise.all(promises).then(function(messages) {
                    self.write({
                        'channel.post': {
                            channel: channel,
                            encrypted: messages,
                            emote: false
                        }
                    });
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
        }
    }
});
