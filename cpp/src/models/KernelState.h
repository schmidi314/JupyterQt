#pragma once

#include <QObject>
#include <QString>

enum class KernelStatus {
    Disconnected,
    Connecting,
    Idle,
    Busy,
    Restarting,
    Error
};

class KernelStateMachine : public QObject {
    Q_OBJECT
public:
    explicit KernelStateMachine(QObject* parent = nullptr);

    KernelStatus status() const { return m_status; }
    void setStatus(KernelStatus status);

    static QString statusToString(KernelStatus status);

signals:
    void statusChanged(KernelStatus status);

private:
    KernelStatus m_status = KernelStatus::Disconnected;
};
