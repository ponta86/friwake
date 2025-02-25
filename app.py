from flask import Flask, render_template, request, jsonify, send_file
import os
import shutil
import tensorflow as tf
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # GUI を使わずにバックエンドで描画
import matplotlib.pyplot as plt
from tensorflow.keras.preprocessing import image
import h5py
import random

app = Flask(__name__)

MODEL_FOLDER = "./model"
models = {}
progress = {"current": 0, "total": 1}  # 初期状態
abort_evaluation = False  # 追加: 中止フラグ

IMAGE_FOLDER = "static/images"  # 背景画像を保存するフォルダ

# モデルをロードする関数
def load_models():
    global models
    models = {}  # 既存のモデルをクリア
    model_info = {}

    for filename in os.listdir(MODEL_FOLDER):
        if filename.endswith(".h5"):
            model_path = os.path.join(MODEL_FOLDER, filename)
            model = tf.keras.models.load_model(model_path)

            # --- h5py でメタデータを取得 ---
            with h5py.File(model_path, "r") as f:
                loaded_label = f.attrs.get("model_label", filename)  # デフォルトはファイル名

            # モデルの入力サイズを取得
            input_size = (224, 224)  # デフォルトサイズ
            if len(model.input_shape) == 4:
                input_size = (model.input_shape[1], model.input_shape[2])  # (height, width)

            print(f"Loaded Model: {filename}, Label: {loaded_label}, Input Size: {input_size}")

            models[filename] = {
                "model": model,  # ここでモデルオブジェクトを保持
                "model_label": loaded_label,
                "input_size": input_size
            }

    return models  # {ファイル名: {model, model_label, input_size}}
# アプリ起動時にモデルをロード
load_models()

@app.route('/')
def index():
    # 画像フォルダ内の画像を取得（jpg, jpeg, png, gif のみ）
    images = [f for f in os.listdir(IMAGE_FOLDER) if f.endswith(('jpg', 'jpeg', 'png', 'gif'))]
    
    # ランダムな画像を選択
    if images:
        random_image = random.choice(images)
        image_path = f"{IMAGE_FOLDER}/{random_image}"
    else:
        image_path = "static/images/default.jpg"  # 画像がない場合のデフォルト

    return render_template('index.html', background_image=image_path)
    return render_template('index.html')

@app.route('/load_models', methods=['POST'])
def load_models_api():
    loaded_models = load_models()  # {モデル名: 入力サイズ} の辞書が返る
    print(loaded_models)
    return jsonify({
        'models': {k: {"model_label": v["model_label"], "input_size": v["input_size"]} for k, v in loaded_models.items()}
    })  # フロントエンドが期待する形式に変換


@app.route('/evaluate', methods=['POST'])
def evaluate():
    global progress, abort_evaluation
    abort_evaluation = False  # ここでフラグをリセット
    image_folder = request.form['image_folder']
    output_folder = request.form['output_folder']
    output_csv = os.path.join(output_folder, "evaluation_results.csv")
    weights = {model: float(request.form.get(model, 1.0)) for model in models}
    # ユーザーが設定した閾値を取得
    threshold = float(request.form.get("threshold", 0.5))  # デフォルトは 0.5
    # 重みを正規化
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}

    good_folder = os.path.join(output_folder, "good")
    bad_folder = os.path.join(output_folder, "bad")
    os.makedirs(good_folder, exist_ok=True)
    os.makedirs(bad_folder, exist_ok=True)

    progress["total"] = len(os.listdir(image_folder))
    progress["current"] = 0  # 進捗リセット

    results = []
    for filename in os.listdir(image_folder):
        if abort_evaluation:  # 中断フラグチェック
            return jsonify({'message': 'Evaluation aborted'})
        img_path = os.path.join(image_folder, filename)
        progress["current"] = progress["current"] + 1  # 進捗更新
        if os.path.isfile(img_path):
            try:
                # モデルの最初の入力サイズを取得 (全モデル共通)
                default_input_size = next(iter(models.values()))["input_size"]
                img = image.load_img(img_path, target_size=default_input_size)
            except Exception as e:
                print(f"Error loading {img_path}: {e}")
                continue

            img_array = image.img_to_array(img) / 255.0
            img_array = np.expand_dims(img_array, axis=0)

            scores = {}
            total_score = 0.0
            for model_name, model_data in models.items():
                model = model_data["model"]
                raw_score = model.predict(img_array)[0][0]
                score = 1 / (1 + np.exp(-raw_score))  # Sigmoidを適用
                scores[model_name] = score
                total_score += score * weights.get(model_name, 1.0 / len(models))

            category = "Good" if total_score > threshold else "Bad"
            dest_folder = good_folder if total_score > threshold else bad_folder
            shutil.copy2(img_path, os.path.join(dest_folder, filename))
            results.append([filename, *scores.values(), total_score, category])

    df = pd.DataFrame(results, columns=["Image", *models.keys(), "Total Score", "Category"])
    df.to_csv(output_csv, index=False)

    # グラフ作成
    plt.figure(figsize=(10, 5))
    df["Total Score"].hist(bins=10, alpha=0.7, color='blue', edgecolor='black')
    plt.axvline(x=threshold, color='red', linestyle='dashed', linewidth=2, label='Threshold')
    plt.xlabel("Total Score")
    plt.ylabel("Number of Images")
    plt.title("Distribution of Image Scores")
    plt.legend()
    graph_path = os.path.join(output_folder, "score_distribution.png")
    plt.savefig(graph_path)

    return jsonify({'message': 'Evaluation complete', 'csv_path': output_csv, 'good_folder': good_folder, 'bad_folder': bad_folder, 'graph_path': graph_path})

@app.route('/get_graph', methods=['GET'])
def get_graph():
    graph_path = request.args.get('path')
    return send_file(graph_path, mimetype='image/png')

@app.route('/stop_evaluation', methods=['POST'])
def stop_evaluation():
    global abort_evaluation
    abort_evaluation = True  # 中止フラグを立てる
    return jsonify({'message': 'Evaluation stopping...'})

@app.route('/progress', methods=['GET'])
def get_progress():
    return jsonify(progress)

if __name__ == '__main__':
    app.run(debug=True)
