#include "KernelState.h"

KernelStateMachine::KernelStateMachine(QObject* parent)
    : QObject(parent)
{
}

void KernelStateMachine::setStatus(KernelStatus status) {
    if (m_status != status) {
        m_status = status;
        emit statusChanged(status);
    }
}

QString KernelStateMachine::statusToString(KernelStatus status) {
    switch (status) {
        case KernelStatus::Disconnected: return QStringLiteral("Disconnected");
        case KernelStatus::Connecting:   return QStringLiteral("Connecting");
        case KernelStatus::Idle:         return QStringLiteral("Idle");
        case KernelStatus::Busy:         return QStringLiteral("Busy");
        case KernelStatus::Restarting:   return QStringLiteral("Restarting");
        case KernelStatus::Error:        return QStringLiteral("Error");
    }
    return QStringLiteral("Unknown");
}
