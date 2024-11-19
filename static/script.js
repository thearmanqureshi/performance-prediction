document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const resultDiv = document.getElementById('result');
    const resultText = document.getElementById('prediction-result');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        resultText.textContent = "Processing...";
        resultDiv.classList.add("loading");

        // Create JSON data from the form inputs
        const formData = new FormData(form);
        const jsonData = {};
        formData.forEach((value, key) => {
            jsonData[key] = key === 'name' ? value : parseFloat(value) || 0; 
        });

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(jsonData),
            });

            if (!response.ok) {
                const errorMessage = `HTTP Error: ${response.status}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();
            if (data.prediction) {
                resultText.textContent = `Predicted Final Marks: ${data.prediction}`;
            } else {
                resultText.textContent = `Error: ${data.error || "Unexpected error occurred"}`;
            }
        } catch (error) {
            console.error('Error:', error.message || error);
            resultText.textContent = 'An error occurred while processing your request.';
        } finally {
            resultDiv.classList.remove("loading");
        }
    });
});
