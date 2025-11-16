package th.ac.mfu.repoai.domain;

import java.util.List;

public class BranchPushRequest {
    public String owner;
    public String repo;
    public String baseBranch;
    public String newBranch;
    public String commitMessage;
    public List<FileChange> fileChanges; // path and base64 content for each file

    public static class FileChange {
        public String path;
        public String base64Content;
    }
}