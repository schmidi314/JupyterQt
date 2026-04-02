#pragma once

#include <QWidget>
#include <QLabel>
#include "models/KernelState.h"

class LedIndicator : public QWidget {
    Q_OBJECT
public:
    explicit LedIndicator(QWidget* parent = nullptr);
    void setColor(const QColor& color);
protected:
    void paintEvent(QPaintEvent* event) override;
private:
    QColor m_color{Qt::gray};
};

class KernelStatusWidget : public QWidget {
    Q_OBJECT
public:
    explicit KernelStatusWidget(QWidget* parent = nullptr);
    void setStatus(KernelStatus status);

private:
    LedIndicator* m_led;
    QLabel*       m_label;
};
