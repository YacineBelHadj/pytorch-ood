import torch
from torch import nn
from torch.optim import Adam
from torch.utils.data import DataLoader
from torchvision.datasets import MNIST, FashionMNIST
from torchvision.transforms import ToTensor

from pytorch_ood.loss import DeepSVDDLoss
from pytorch_ood.utils import OODMetrics, ToUnknown

torch.manual_seed(1234)

device = "cuda:0"


class Model(nn.Module):
    """
    We define a simple model. As described in the original paper of Deep SVDD, this model must not
    use biases in linear layers or convolutions, since this would lead to a trivial solution
    for the optimization problem.
    """

    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv2d(1, 16, 3, padding=1, bias=False)
        self.pool = nn.MaxPool2d(2)
        self.c2 = nn.Conv2d(16, 32, 3, padding=1, bias=False)
        self.c3 = nn.Conv2d(32, 64, 3, padding=1, bias=False)

        self.layer5 = nn.Linear(576, 128, bias=False)
        self.layer6 = nn.Linear(128, 2, bias=False)

    def forward(self, x):
        batch_size = x.shape[0]
        x = self.c1(x).relu()
        x = self.pool(x)
        x = self.c2(x).relu()
        x = self.pool(x)
        x = self.c3(x).relu()
        x = self.pool(x)
        x = x.reshape(batch_size, -1)
        x = self.layer5(x).relu()
        x = self.layer6(x)
        return x


# setup training data
train_dataset = MNIST(root="data", download=True, train=True, transform=ToTensor())
train_loader = DataLoader(train_dataset, num_workers=5, batch_size=128, shuffle=True)

# setup test data, mark FashionMNIST as OOD with ToUnknown()
test_dataset_in = MNIST(root="data", download=True, train=False, transform=ToTensor())
test_dataset_out = FashionMNIST(
    root="data", download=True, train=False, transform=ToTensor(), target_transform=ToUnknown()
)

test_loader = DataLoader(
    test_dataset_out + test_dataset_in, shuffle=False, num_workers=5, batch_size=256
)

# setup model, optimizer and training criterion
model = Model().to(device)
opti = Adam(model.parameters(), lr=0.001)

# initialize the center of SVDD with the mean over the dataset
with torch.no_grad():
    d = [model(x.to(device)) for x, y in train_loader]
    center = torch.concat(d).mean(dim=0).cpu()

print(center)

criterion = DeepSVDDLoss(n_dim=2, center=center).to(device)


def test():
    """
    Test the model and print some metrics
    """
    model.eval()
    metrics = OODMetrics()

    with torch.no_grad():
        for x, y in test_loader:
            z = model(x.to(device))
            # calculate distance to the center, squeeze unused class-dimension (since there is only a single class)
            distances = criterion.center(z).cpu().squeeze()
            metrics.update(distances, y)

    print(metrics.compute())
    model.train()


# Train model and test at the end of each epoch
for epoch in range(20):
    print(f"Epoch {epoch}")
    for x, _ in train_loader:
        z = model(x.to(device))
        # since this is a one-class method, we do not have to provide any class labels
        loss = criterion(z)
        opti.zero_grad()
        loss.backward()
        opti.step()

    test()
