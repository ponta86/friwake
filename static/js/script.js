document.getElementById("model-form").onsubmit = function(e) {
    e.preventDefault();
    fetch("/load_models", {
        method: "POST",
        body: new URLSearchParams({"model_folder": "fixed_model_path"})
    })
    .then(response => response.json())
    .then(data => {
        console.log("✅ API Response:", data); // デバッグ: API のレスポンス確認

        let modelsDiv = document.getElementById("model-weights");
        modelsDiv.innerHTML = ""; // クリア

        // data.models は辞書なので、Object.entries() を使う
        Object.entries(data.models).forEach(([filename, modelData]) => {
            console.log("📂 Model Loaded:", filename, modelData); // 各モデルのデータ確認

            //modelsDiv.innerHTML += `<label>${modelData.model_label} (${filename}): 
            modelsDiv.innerHTML += `<label>${modelData.model_label}: 
                <input type="number" step="1" name="${filename}" value="100" class="weight-input"></label><br>`;
        });

        addWeightValidation();
    })
    .catch(error => console.error("❌ Error loading models:", error));
};

function addWeightValidation() {
    const inputs = document.querySelectorAll(".weight-input");
    const evaluateButton = document.getElementById("evaluate-button");
    const errorText = document.getElementById("weight-error");

    function validateWeights() {
        let total = 0;
        inputs.forEach(input => total += parseInt(input.value) || 0);
        
        if (total === 100) {
            evaluateButton.disabled = false;
            errorText.style.display = "none";
        } else {
            evaluateButton.disabled = true;
            errorText.style.display = "block";
            errorText.textContent = `Total weight must be exactly 100% (Current: ${total}%)`;
        }
    }

    inputs.forEach(input => {
        input.addEventListener("input", validateWeights);
    });

    validateWeights();
}

document.getElementById("evaluation-form").onsubmit = function (e) {
    e.preventDefault();
    let evaluateButton = document.getElementById("evaluate-button");
    let formData = new FormData(e.target);
	formData.append("threshold", document.getElementById("threshold").value);

	let progressBar = document.getElementById("progress-bar");
    let progressText = document.getElementById("progress-text");
    // 進捗バーをリセット
    progressBar.style.width = "0%";

    progressText.textContent = "Processing...";
    if (evaluateButton.dataset.running === "true") {
        // すでに実行中なら、ストップAPIを呼ぶ
        fetch("/stop_evaluation", { method: "POST" })
            .then(response => response.json())
            .then(data => {
                evaluateButton.textContent = "Evaluate";
                evaluateButton.dataset.running = "false";
                progressText.textContent = "Evaluation stopped.";
            })
            .catch(error => console.error("Error stopping evaluation:", error));
        return;
    }

    // 新しく評価を開始する
    fetch("/evaluate", {
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
    })
    .catch(error => console.error("Evaluation error:", error));

    evaluateButton.textContent = "Stop";
    evaluateButton.dataset.running = "true";

    function updateProgress() {
        fetch("/progress")
            .then(response => response.json())
            .then(progress => {
                let percent = (progress.current / progress.total) * 100;
                progressBar.style.width = percent + "%";
                progressText.textContent = `Processing ${progress.current} / ${progress.total} images`;

                if (progress.current < progress.total && evaluateButton.dataset.running === "true") {
                    setTimeout(updateProgress, 500);
                } else {
                    evaluateButton.textContent = "Evaluate";
                    evaluateButton.dataset.running = "false";
                    progressText.textContent = "Evaluation complete!";
                }
            });
    }

    // **修正ポイント: 進捗チェックを開始**
    setTimeout(updateProgress, 500);
};

