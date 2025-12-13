## Contributing

This project is Source-Available. We welcome contributions from the community!

Please Note: This is a commercial project owned by Boundless Games, LLC. To ensure the long-term sustainability of the project, all contributors must sign a Contributor Assignment Agreement (CAA) transferring ownership of their contribution to the Company.

This is a volunteer-only opportunity.

You will be prompted to sign the agreement digitally via our CLA bot when you open a Pull Request.

Please do not contribute if you expect compensation or employment.

## 🤝 How to Contribute
We welcome contributions to gaia-free! Whether it's fixing a bug or adding a new feature, your help is appreciated.

To ensure we can accept your code, all contributors are required to sign a standard Contributor License Agreement (CLA). You will be prompted to sign this digitally when you open your first Pull Request.

## The "Fork & Pull" Workflow
We use the standard GitHub "Fork and Pull" workflow. This means you will work on your own copy of the repository and request that we merge your changes.

### Step 1: Fork the Repository
Click the Fork button in the top-right corner of this page.

This creates a copy of gaia-free in your own GitHub account (e.g., YourUsername/gaia-free).

### Step 2: Clone Your Fork
Open your terminal and clone your fork (not the main repo):

```bash
# Replace 'YourUsername' with your actual GitHub username
git clone https://github.com/YourUsername/gaia-free.git
cd gaia-free
```

### Step 3: Set Up "Upstream" Sync
To easily get updates from the main project, link the original repository as a remote named upstream:

```bash
git remote add upstream https://github.com/Boundless-Studios/gaia-free.git
```

### Step 4: Create a Branch
Never work directly on the main branch. Always create a new branch for your specific feature or fix:

```bash
# Good branch names: fix-login-bug, add-inventory-ui
git checkout -b my-new-feature
```

### Step 5: Code & Push
Make your changes, save them, and commit them. When you are ready, push the branch to your fork:

```bash
git add .
git commit -m "Fixed the login glitch"
git push origin my-new-feature
```

### Step 6: Open a Pull Request (PR)
Go to your fork on GitHub (github.com/YourUsername/gaia-free).

You should see a banner saying "Your branch is ahead of Boundless-Studios:main".

Click Contribute -> Open Pull Request.

Fill in the details of what you fixed.

### Step 7: Accept the CLA
Once you open the PR, a bot named CLA Assistant will post a comment on your request.

Click the link provided by the bot in the comment.

Digitally sign the agreement with your GitHub account.

Once signed, the PR check will turn Green, and we can review your code!

## 🔄 Keeping Your Fork in Sync
The main gaia-free repository changes often. If your fork gets out of date, you may encounter conflicts. Here is how to keep it updated:

### Option A: The GitHub UI (Easiest)

1. Go to your fork on GitHub.
2. Click the "Sync fork" button (usually under the green "Code" button).
3. In your terminal, run `git pull origin main` to download those updates to your computer.

### Option B: Command Line (Standard)

```bash
# 1. Fetch the latest changes from the main project
git fetch upstream

# 2. Switch to your main branch
git checkout main

# 3. Merge the main project's changes into your local main
git merge upstream/main

# 4. Push the updates to your GitHub fork
git push origin main
```
