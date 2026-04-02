#pragma once

#include <QString>

struct ServerConfig {
    QString baseUrl;   // e.g. "http://localhost:8888"
    QString token;     // Jupyter API token

    QString apiUrl() const {
        return baseUrl + "/api";
    }

    QString wsUrl() const {
        QString ws = baseUrl;
        ws.replace(QStringLiteral("http://"), QStringLiteral("ws://"));
        ws.replace(QStringLiteral("https://"), QStringLiteral("wss://"));
        return ws;
    }

    bool isValid() const {
        return !baseUrl.isEmpty();
    }
};
