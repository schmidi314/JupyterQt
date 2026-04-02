#include "NotebookController.h"
#include <QJsonDocument>
#include <QNetworkReply>

NotebookController::NotebookController(const QString& notebookId,
                                         RestClient* restClient,
                                         ExecutionTracker* tracker,
                                         QObject* parent)
    : QObject(parent)
    , m_notebookId(notebookId)
    , m_notebook(new NotebookModel(this))
    , m_kernelClient(new KernelClient(this))
    , m_kernelState(new KernelStateMachine(this))
    , m_restClient(restClient)
    , m_tracker(tracker)
{
    connect(m_notebook, &NotebookModel::cellAdded,   this, &NotebookController::cellAdded);
    connect(m_notebook, &NotebookModel::cellRemoved, this, &NotebookController::cellRemoved);
    connect(m_kernelState, &KernelStateMachine::statusChanged,
            this, &NotebookController::kernelStatusChanged);

    connectKernelSignals();
}

NotebookController::~NotebookController() {
    m_tracker->cancelAllForNotebook(m_notebookId);
}

void NotebookController::connectKernelSignals() {
    connect(m_kernelClient, &KernelClient::connected,
            this, &NotebookController::onKernelConnected);
    connect(m_kernelClient, &KernelClient::disconnected,
            this, &NotebookController::onKernelDisconnected);
    connect(m_kernelClient, &KernelClient::kernelStatusChanged,
            this, &NotebookController::onKernelStatusChanged);
    connect(m_kernelClient, &KernelClient::streamOutput,
            this, &NotebookController::onStreamOutput);
    connect(m_kernelClient, &KernelClient::displayData,
            this, &NotebookController::onDisplayData);
    connect(m_kernelClient, &KernelClient::executeResult,
            this, &NotebookController::onExecuteResult);
    connect(m_kernelClient, &KernelClient::executeError,
            this, &NotebookController::onExecuteError);
    connect(m_kernelClient, &KernelClient::executeReply,
            this, &NotebookController::onExecuteReply);
}

void NotebookController::load(const QString& path, const ServerConfig& config) {
    m_config = config;
    m_notebook->setPath(path);
    m_kernelState->setStatus(KernelStatus::Connecting);

    auto* reply = m_restClient->getNotebook(path);
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        if (reply->error() != QNetworkReply::NoError) {
            emit notebookError(reply->errorString());
            m_kernelState->setStatus(KernelStatus::Error);
            return;
        }
        auto data = reply->readAll();
        auto doc = QJsonDocument::fromJson(data);
        if (!doc.isObject()) {
            emit notebookError(QStringLiteral("Invalid notebook JSON"));
            m_kernelState->setStatus(KernelStatus::Error);
            return;
        }
        auto nbObj = doc.object()[QStringLiteral("content")].toObject();
        m_notebook->loadFromJson(nbObj);
        emit notebookLoaded();
        startKernel();
    });
}

void NotebookController::startKernel() {
    m_kernelState->setStatus(KernelStatus::Connecting);
    auto* reply = m_restClient->startKernel(m_notebook->kernelName());
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        if (reply->error() != QNetworkReply::NoError) {
            emit notebookError(reply->errorString());
            m_kernelState->setStatus(KernelStatus::Error);
            return;
        }
        auto data = reply->readAll();
        auto doc = QJsonDocument::fromJson(data);
        if (!doc.isObject()) {
            emit notebookError(QStringLiteral("Invalid kernel response"));
            m_kernelState->setStatus(KernelStatus::Error);
            return;
        }
        QString kernelId = doc.object()[QStringLiteral("id")].toString();
        m_notebook->setKernelId(kernelId);
        m_kernelClient->connectToKernel(m_config, kernelId);
    });
}

void NotebookController::save() {
    auto* reply = m_restClient->saveNotebook(m_notebook->path(), m_notebook->toJson());
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        if (reply->error() != QNetworkReply::NoError) {
            emit notebookError(reply->errorString());
            return;
        }
        emit notebookSaved();
    });
}

void NotebookController::executeCell(const QString& cellId) {
    auto* cell = m_notebook->cell(cellId);
    if (!cell || cell->cellType() != CellType::Code) return;

    // Enqueue if already executing
    if (!m_currentExecutingCellId.isEmpty()) {
        if (!m_executionQueue.contains(cellId)) {
            m_executionQueue.enqueue(cellId);
        }
        return;
    }

    doExecuteCell(cell);
}

void NotebookController::doExecuteCell(CellModel* cell) {
    if (!m_kernelClient->isConnected()) return;

    m_currentExecutingCellId = cell->cellId();
    cell->clearOutputs();
    cell->setExecuting(true);

    emit cellOutputsCleared(cell->cellId());
    emit cellExecutingChanged(cell->cellId(), true);

    QString msgId = m_kernelClient->executeCode(cell->source());
    m_tracker->track(msgId, cell, m_notebookId);
}

void NotebookController::executeAllCells() {
    m_executionQueue.clear();
    bool first = true;
    for (auto* cell : m_notebook->cells()) {
        if (cell->cellType() != CellType::Code) continue;
        if (first) {
            first = false;
            m_currentExecutingCellId.clear();
            doExecuteCell(cell);
        } else {
            m_executionQueue.enqueue(cell->cellId());
        }
    }
}

void NotebookController::interruptKernel() {
    if (m_notebook->kernelId().isEmpty()) return;
    auto* reply = m_restClient->interruptKernel(m_notebook->kernelId());
    connect(reply, &QNetworkReply::finished, reply, &QNetworkReply::deleteLater);
}

void NotebookController::restartKernel() {
    m_executionQueue.clear();
    m_tracker->cancelAllForNotebook(m_notebookId);
    m_currentExecutingCellId.clear();
    m_kernelState->setStatus(KernelStatus::Restarting);

    if (m_notebook->kernelId().isEmpty()) return;
    auto* reply = m_restClient->restartKernel(m_notebook->kernelId());
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        m_kernelState->setStatus(KernelStatus::Idle);
    });
}

void NotebookController::restartKernelAndRun() {
    m_restartAndRun = true;
    restartKernel();
    // executeAllCells will be called when kernel becomes idle after restart
}

void NotebookController::shutdownKernel() {
    m_executionQueue.clear();
    m_tracker->cancelAllForNotebook(m_notebookId);
    m_currentExecutingCellId.clear();
    m_kernelClient->disconnectFromKernel();

    if (m_notebook->kernelId().isEmpty()) return;
    auto* reply = m_restClient->shutdownKernel(m_notebook->kernelId());
    connect(reply, &QNetworkReply::finished, reply, &QNetworkReply::deleteLater);
}

void NotebookController::addCell(CellType type, int index) {
    m_notebook->addCell(type, index);
}

void NotebookController::addCellAbove(const QString& refCellId, CellType type) {
    int idx = m_notebook->cellIndex(refCellId);
    m_notebook->addCell(type, idx);
}

void NotebookController::addCellBelow(const QString& refCellId, CellType type) {
    int idx = m_notebook->cellIndex(refCellId);
    m_notebook->addCell(type, idx + 1);
}

void NotebookController::removeCell(const QString& cellId) {
    if (m_notebook->cells().size() <= 1) return;
    if (m_currentExecutingCellId == cellId) {
        interruptKernel();
        m_currentExecutingCellId.clear();
    }
    m_executionQueue.removeAll(cellId);
    m_notebook->removeCell(cellId);
}

void NotebookController::setCellSource(const QString& cellId, const QString& source) {
    auto* cell = m_notebook->cell(cellId);
    if (!cell) return;
    cell->setSource(source);
    emit cellSourceChanged(cellId, source);
}

void NotebookController::setCellType(const QString& cellId, CellType type) {
    auto* cell = m_notebook->cell(cellId);
    if (!cell) return;
    cell->setCellType(type);
}

void NotebookController::startNextExecution() {
    m_currentExecutingCellId.clear();
    if (m_executionQueue.isEmpty()) return;

    QString nextId = m_executionQueue.dequeue();
    auto* cell = m_notebook->cell(nextId);
    if (cell) {
        doExecuteCell(cell);
    } else {
        startNextExecution();
    }
}

// Kernel event slots

void NotebookController::onKernelConnected() {
    m_kernelState->setStatus(KernelStatus::Idle);
    if (m_restartAndRun) {
        m_restartAndRun = false;
        executeAllCells();
    }
}

void NotebookController::onKernelDisconnected() {
    m_kernelState->setStatus(KernelStatus::Disconnected);
    m_currentExecutingCellId.clear();
}

void NotebookController::onKernelStatusChanged(const QString& execState) {
    if (execState == QLatin1String("idle")) {
        m_kernelState->setStatus(KernelStatus::Idle);
    } else if (execState == QLatin1String("busy")) {
        m_kernelState->setStatus(KernelStatus::Busy);
    } else if (execState == QLatin1String("starting")) {
        m_kernelState->setStatus(KernelStatus::Connecting);
    }
}

void NotebookController::onStreamOutput(const QString& name, const QString& text,
                                         const QString& parentMsgId)
{
    auto* cell = m_tracker->cell(parentMsgId);
    if (!cell) return;

    OutputItem item;
    item.output_type = QStringLiteral("stream");
    item.name = name;
    item.text = text;
    cell->appendOutput(item);
    emit cellOutputAppended(cell->cellId(), item);
}

void NotebookController::onDisplayData(const QJsonObject& data, const QString& parentMsgId) {
    auto* cell = m_tracker->cell(parentMsgId);
    if (!cell) return;

    OutputItem item;
    item.output_type = QStringLiteral("display_data");
    item.data = data;
    cell->appendOutput(item);
    emit cellOutputAppended(cell->cellId(), item);
}

void NotebookController::onExecuteResult(const QJsonObject& data, int execCount,
                                          const QString& parentMsgId)
{
    auto* cell = m_tracker->cell(parentMsgId);
    if (!cell) return;

    OutputItem item;
    item.output_type = QStringLiteral("execute_result");
    item.data = data;
    item.execution_count = execCount;
    cell->appendOutput(item);
    emit cellOutputAppended(cell->cellId(), item);
}

void NotebookController::onExecuteError(const QString& ename, const QString& evalue,
                                         const QStringList& traceback,
                                         const QString& parentMsgId)
{
    auto* cell = m_tracker->cell(parentMsgId);
    if (!cell) return;

    OutputItem item;
    item.output_type = QStringLiteral("error");
    item.ename = ename;
    item.evalue = evalue;
    item.traceback = traceback;
    cell->appendOutput(item);
    emit cellOutputAppended(cell->cellId(), item);
}

void NotebookController::onExecuteReply(const QString& parentMsgId, int execCount,
                                         const QString& status)
{
    Q_UNUSED(status)
    auto* cell = m_tracker->cell(parentMsgId);
    if (cell) {
        cell->setExecutionCount(execCount);
        cell->setExecuting(false);
        emit cellExecutionCountUpdated(cell->cellId(), execCount);
        emit cellExecutingChanged(cell->cellId(), false);
    }
    m_tracker->cancel(parentMsgId);
    startNextExecution();
}
