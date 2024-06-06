from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from .models import GithubRepo
from accounts.models import GitHubUser
from .serializers import GithubRepoSerializer
import requests
from datetime import datetime
from django.utils import timezone
from django.db.models import F


class GitHubRepositoriesView(View):
    """A class-based view for retrieving GitHub repositories."""

    def get(self, request):        
        repositories = GithubRepo.objects.fetch_repos()
        if not repositories:
            return JsonResponse(
                {"error": "Failed to fetch GitHub repositories"}, status=500
            )

        repositories = GithubRepo.objects.prioritize_hacktoberfest_repos(repositories)
        popular_repo_result = GithubRepo.objects.get_popular_repos(repositories)
        featured_repo_result = GithubRepo.objects.get_featured_repo(popular_repo_result)
        latest_contributors_result = GithubRepo.objects.get_latest_contributors(repositories)
        serialized_repos = GithubRepoSerializer(repositories, many=True).data

        repo_data = {
            "popular_repos_result": popular_repo_result,
            "featured_repo_result": featured_repo_result,
            "latest_contributors_result": latest_contributors_result,
            "repositories": serialized_repos,
        }

        return JsonResponse(repo_data, safe=True, status=200)

class GitHubUserContributionView(View):
    """A class-based view for retrieving user contributions."""
    
    def get_github_username(self, user_access_token):
        url = 'https://api.github.com/user'
        headers = {
            'Authorization': f'Bearer {user_access_token}'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            return response_json['login']
        except requests.exceptions.RequestException as e:
            print(f'Failed to fetch GitHub user: {e}')
            return None

    def get_user_repositories(self, user_access_token):
        url = 'https://api.github.com/user/repos'
        headers = {
            'Authorization': f'Bearer {user_access_token}'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Failed to fetch user repositories: {e}')
            return None

    def get_repository_commits(self, owner, repo, user_access_token):

        # print('get_repository_commits function called\n')
        
        url = f'https://api.github.com/repos/{owner}/{repo}/commits'
        headers = {
            'Authorization': f'Bearer {user_access_token}'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Failed to fetch commits for {owner}/{repo}: {e}')
            return None


    def get(self, request):
        
        user_access_token = request.headers.get('Authorization')

        if not user_access_token:
            return JsonResponse({'error': 'Access token not provided'}, status=400)

        if user_access_token.startswith('Bearer '):
            user_access_token = user_access_token.split(' ')[1]

        github_username = self.get_github_username(user_access_token)

        if not github_username:
            return JsonResponse({'error': 'Failed to retrieve GitHub username'}, status=500)

        repositories = self.get_user_repositories(user_access_token)

        if not repositories:
            return JsonResponse({'error': 'Failed to retrieve user repositories'}, status=500)

        # Initialize commit count
        new_commit_count = 0


         # Fetch the user's last login time
        try:
            github_user = GitHubUser.objects.get(github_username=github_username)
            last_login_time = github_user.last_login.replace(tzinfo=None)
            print('*** last_login_time to OSD', github_user, last_login_time)

        except GitHubUser.DoesNotExist:
            return JsonResponse({'error': 'GitHub user not found'}, status=404)

        user_contribution_data = []
        
        for repo in repositories:
            owner = repo['owner']['login']
            repo_name = repo['name']
            commits = self.get_repository_commits(owner, repo_name, user_access_token)

            if commits:
                commits.sort(key=lambda x: x["commit"]["author"]["date"], reverse=True)


                for commit in commits:
                    commit_date = datetime.strptime(commit["commit"]["author"]["date"], "%Y-%m-%dT%H:%M:%SZ")
                    
                    if commit_date > last_login_time:
                        new_commit_count += 1
                        print('*** new_commit_count + 1!')
                        print('*** Repo name:', repo_name)
                        print("*** commit_date ", commit_date)
                        print("*** commit_message ", commit["commit"]["message"])
                                
                    user_contribution_data.append({
                        "commit_date": commit["commit"]["author"]["date"],
                        "commit_message": commit["commit"]["message"],
                        "repository": {
                            "repo_id": repo["id"],
                            "repo_name": repo["name"],
                            "repo_full_name": repo["full_name"],
                            "repo_avatar_url": repo["owner"]["avatar_url"],
                            "repo_html_url": repo["html_url"],
                            "repo_labels_url": repo["labels_url"].replace('{/name}', ''),
                        }
                    })

        user_contribution_data.sort(key=lambda x: x["commit_date"], reverse=True) # Keep this line to sort commits from newest to oldest

        # print('*** User contribution data', user_contribution_data[:3])
    
        # Update the user's opensource_commit_count
        # print('*** total new_commit_count', new_commit_count)

        if new_commit_count > 0:
            
            GitHubUser.objects.filter(github_username=github_username).update(
                opensource_commit_count=F('opensource_commit_count') + new_commit_count
            )
            
            github_user = GitHubUser.objects.get(github_username=github_username)

        # print('*** User contribution data', user_contribution_data)

        github_user.last_login = timezone.now()
        github_user.save()

        # Not necessary to return the user_contribution_data. 
        # This function should just update the opensource_contribution_data in the database. Another frontend axios call could retrieve the opensource_contribution_data from the database. 
        return JsonResponse(user_contribution_data, safe=False, status=200)


    def check_user_commits(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        github_user = request.user
        if not github_user.user_name:
            return JsonResponse({'error': 'GitHub username not set'}, status=400)

        repo_manager = GithubRepo.objects
        has_user_commits, commit_count = repo_manager.check_user_commits(github_user.user_name, github_user.registration_date)

        if has_user_commits:
            github_user.opensource_commit_count = commit_count
            github_user.save()
            return JsonResponse({"message": "User has commits in the repositories"}, status=200)
        else:
            return JsonResponse({"message": "User has no commits in the repositories"}, status=200)
