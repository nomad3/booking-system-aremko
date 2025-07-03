## Helm Chart for Aremko Booking System

This directory contains a Helm chart for deploying the Aremko Booking System to a Kubernetes cluster.

### Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- A running Kubernetes cluster (e.g., GKE)
- A container registry (e.g., Google Container Registry) to store the application's Docker image.

### Chart Structure

- `charts/`: This directory contains the Helm chart.
  - `Chart.yaml`: Metadata about the chart.
  - `values.yaml`: Default configuration values for the chart.
  - `templates/`: Directory for Kubernetes manifest templates.
    - `_helpers.tpl`: Template helpers.
    - `deployment.yaml`: Deployment template.
    - `service.yaml`: Service template.
    - `ingress.yaml`: Ingress template.
    - `configmap.yaml`: ConfigMap template.
    - `secret.yaml`: Secret template.

### Getting Started

1.  **Build and Push the Docker Image:**

    Build the Docker image for the application and push it to your container registry.

    ```bash
    docker build -t your-registry/aremko-booking-system:latest .
    docker push your-registry/aremko-booking-system:latest
    ```

2.  **Update `values.yaml`:**

    Update the `charts/values.yaml` file with the correct values for your environment. At a minimum, you should update the following:

    - `image.repository`: The URL of your container registry.
    - `image.tag`: The tag of the Docker image to deploy.
    - `ingress.hosts`: The hostname for the application.
    - `secret.data`: The sensitive data for the application (e.g., database credentials, Django secret key). It is recommended to manage secrets using a more secure method like Sealed Secrets or Vault.

3.  **Install the Chart:**

    Install the Helm chart to your Kubernetes cluster.

    **For `dev` environment:**

    ```bash
    helm install my-release-dev ./charts -f ./charts/values.yaml \
      --set image.tag=dev \
      --set ingress.hosts[0].host=dev.aremko.yourdomain.com
    ```

    **For `prod` environment:**

    ```bash
    helm install my-release-prod ./charts -f ./charts/values.yaml \
      --set image.tag=main \
      --set replicaCount=2 \
      --set ingress.hosts[0].host=aremko.yourdomain.com
    ```

    Replace `my-release-dev`, `my-release-prod`, `dev.aremko.yourdomain.com`, and `aremko.yourdomain.com` with your desired release names and domain names.

### Configuration

The following table lists the configurable parameters of the chart and their default values.

| Parameter                      | Description                                     | Default                                       |
| ------------------------------ | ----------------------------------------------- | --------------------------------------------- |
| `replicaCount`                 | Number of replicas for the deployment.          | `1`                                           |
| `image.repository`             | Image repository.                               | `gcr.io/your-gcp-project-id/aremko-booking-system` |
| `image.pullPolicy`             | Image pull policy.                              | `IfNotPresent`                                |
| `image.tag`                    | Image tag.                                      | `""`                                          |
| `service.type`                 | Service type.                                   | `ClusterIP`                                   |
| `service.port`                 | Service port.                                   | `8000`                                        |
| `ingress.enabled`              | Enable/disable Ingress.                         | `false`                                       |
| `ingress.hosts`                | Ingress host configuration.                     | `chart-example.local`                         |
| `configMap.data`               | Data for the ConfigMap.                         | `{}`                                          |
| `secret.data`                  | Data for the Secret.                            | `{}`                                          |

</rewritten_file> 