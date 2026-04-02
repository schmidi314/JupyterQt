#pragma once

#include <QObject>
#include <QQueue>
#include <QString>
#include "models/NotebookModel.h"
#include "models/KernelState.h"
#include "models/CellModel.h"
#include "jupyter/KernelClient.h"
#include "jupyter/ExecutionTracker.h"
#include "network/RestClient.h"
#include "config/ServerConfig.h"

class NotebookController : public QObject {
    Q_OBJECT
public:
    explicit NotebookController(const QString& notebookId,
                                 RestClient* restClient,
                                 ExecutionTracker* tracker,
                                 QObject* parent = nullptr);
    ~NotebookController() override;

    QString notebookId() const { return m_notebookId; }
    NotebookModel* notebookModel() { return m_notebook; }
    KernelStateMachine* kernelState() { return m_kernelState; }
    KernelStatus kernelStatus() const { return m_kernelState->status(); }

    // Actions
    void load(const QString& path, const ServerConfig& config);
    void save();
    void executeCell(const QString& cellId);
    void executeAllCells();
    void interruptKernel();
    void restartKernel();
    void restartKernelAndRun();
    void shutdownKernel();

    // Cell editing
    void addCell(CellType type, int index = -1);
    void addCellAbove(const QString& refCellId, CellType type);
    void addCellBelow(const QString& refCellId, CellType type);
    void removeCell(const QString& cellId);
    void setCellSource(const QString& cellId, const QString& source);
    void setCellType(const QString& cellId, CellType type);

signals:
    void cellOutputAppended(const QString& cellId, const OutputItem& item);
    void cellOutputsCleared(const QString& cellId);
    void cellExecutionCountUpdated(const QString& cellId, int count);
    void cellExecutingChanged(const QString& cellId, bool executing);
    void kernelStatusChanged(KernelStatus status);
    void notebookLoaded();
    void notebookSaved();
    void notebookError(const QString& message);
    void cellAdded(int index, CellModel* cell);
    void cellRemoved(const QString& cellId);
    void cellSourceChanged(const QString& cellId, const QString& source);

private slots:
    void onKernelConnected();
    void onKernelDisconnected();
    void onKernelStatusChanged(const QString& execState);
    void onStreamOutput(const QString& name, const QString& text, const QString& parentMsgId);
    void onDisplayData(const QJsonObject& data, const QString& parentMsgId);
    void onExecuteResult(const QJsonObject& data, int execCount, const QString& parentMsgId);
    void onExecuteError(const QString& ename, const QString& evalue,
                        const QStringList& traceback, const QString& parentMsgId);
    void onExecuteReply(const QString& parentMsgId, int execCount, const QString& status);

private:
    void startNextExecution();
    void doExecuteCell(CellModel* cell);
    void startKernel();
    void connectKernelSignals();

    QString m_notebookId;
    NotebookModel* m_notebook;
    KernelClient* m_kernelClient;
    KernelStateMachine* m_kernelState;
    RestClient* m_restClient;
    ExecutionTracker* m_tracker;

    ServerConfig m_config;
    QQueue<QString> m_executionQueue; // queued cell ids
    QString m_currentExecutingCellId;
    bool m_restartAndRun = false;
};
