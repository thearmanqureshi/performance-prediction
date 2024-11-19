document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const resultElement = document.getElementById('prediction-result');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            // Check for response.ok before parsing JSON
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
            }

            const data = await response.json();
            if (data.prediction !== undefined) {
                resultElement.textContent = `Prediction: ${data.prediction}`;
            } else {
                resultElement.textContent = `Error: ${data.error || 'No prediction available'}`;
            }
        } catch (error) {
            console.error("Error:", error);
            resultElement.textContent = `Error: ${error.message}`;
        }
    });
});
