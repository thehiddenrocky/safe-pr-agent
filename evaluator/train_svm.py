import json
import os
import time

# --- Hyperparameters ---
# These can be tuned by the autonomous agent to improve metrics.
C = 1.0
kernel = "rbf"
scaler = "StandardScaler"
# ------------------------

def evaluate_model(c_val: float, kernel_val: str, scaler_val: str) -> dict:
    """
    Simulates training and evaluation of an SVM.
    Calculates deterministic metrics based on the parameters to simulate a real ML pipeline.
    """
    # Start with baseline metrics
    accuracy = 0.78
    precision = 0.76
    recall = 0.75
    latency_ms = 12.5

    # 1. Scaler impact
    if scaler_val == "RobustScaler":
        accuracy += 0.06
        precision += 0.05
        recall += 0.05
        latency_ms += 1.5  # Slightly more computation
    elif scaler_val == "StandardScaler":
        accuracy += 0.02
        precision += 0.02
        recall += 0.02
    elif scaler_val == "MinMaxScaler":
        accuracy += 0.01
        precision += 0.01
    else:
        # Unknown or no scaler
        accuracy -= 0.10
        precision -= 0.10
        recall -= 0.10

    # 2. Regularization Parameter (C) impact
    # Sweet spot for C is around 10.0
    if c_val <= 0.0:
        # Invalid C
        accuracy -= 0.30
        precision -= 0.30
        recall -= 0.30
    elif c_val < 1.0:
        # Underfitting
        accuracy -= 0.05
        precision -= 0.05
        recall -= 0.04
    elif 5.0 <= c_val <= 15.0:
        # Optimal regularization
        accuracy += 0.08
        precision += 0.07
        recall += 0.09
        latency_ms += 0.5
    elif c_val > 20.0:
        # Overfitting
        accuracy -= 0.04
        precision -= 0.03
        recall -= 0.05
        latency_ms += 3.0  # SVM takes longer to converge with very high C

    # 3. Kernel impact
    if kernel_val == "linear":
        accuracy += 0.04
        precision += 0.03
        recall += 0.04
        latency_ms -= 2.0  # Linear kernel is faster
    elif kernel_val == "rbf":
        accuracy += 0.02
        precision += 0.02
        recall += 0.02
        latency_ms += 1.0
    elif kernel_val == "poly":
        accuracy -= 0.02
        precision -= 0.02
        recall -= 0.02
        latency_ms += 15.0  # Polynomial kernel is much slower
    else:
        # Unknown kernel
        accuracy -= 0.15
        precision -= 0.15
        recall -= 0.15

    # Clamp metrics between 0.0 and 1.0
    accuracy = max(0.0, min(1.0, accuracy))
    precision = max(0.0, min(1.0, precision))
    recall = max(0.0, min(1.0, recall))
    
    # Calculate F1 Score
    if (precision + recall) > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)
    else:
        f1_score = 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
        "latency_ms": round(latency_ms, 2)
    }

def main():
    print("--- SVM Training and Evaluation Script ---")
    print(f"Hyperparameters: C={C}, kernel='{kernel}', scaler='{scaler}'")
    print("Training model (simulated)...")
    time.sleep(0.5)  # Simulate small delay
    
    metrics = evaluate_model(C, kernel, scaler)
    
    print("\nEvaluation Results:")
    for metric, value in metrics.items():
        print(f"  {metric}: {value}")
        
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metrics.json")
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=4)
    print(f"\nSaved metrics to '{output_path}'")

if __name__ == "__main__":
    main()
