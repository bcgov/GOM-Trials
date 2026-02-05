//
//  ImagePickerDelegate.m
//  gomapp
//
//  Created by Kiri Daust on 2026-02-02.
//

#import "ImagePickerDelegate.h"
#import "ImagePicker.h"

@implementation ImagePickerDelegate

- (void)imagePickerController:(UIImagePickerController *)picker
didFinishPickingMediaWithInfo:(NSDictionary *)info
{
    NSLog(@"didFinishPickingMediaWithInfo fired");

    // Save image to PNG
    ImagePicker *nip = [[ImagePicker alloc] init];
    NSString *savedPath = [nip writeToJPG:info
                                  quality:0.8
                                   maxDim:1600];
    
    NSLog(@"[ImagePickerDelegate] Saved JPG to: %@", savedPath);

    // Write savedPath into a known result file
    NSString *docs = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,
        NSUserDomainMask, YES).firstObject;

    NSString *ipcDir = [docs stringByAppendingPathComponent:@"gomapp_ipc"];
    [[NSFileManager defaultManager] createDirectoryAtPath:ipcDir
                              withIntermediateDirectories:YES
                                               attributes:nil
                                                    error:nil];

    NSString *resultFile = [ipcDir stringByAppendingPathComponent:@"picker_result.txt"];
    NSLog(@"[ImagePickerDelegate] Writing result to: %@", resultFile);

    NSError *err = nil;
    BOOL ok = [savedPath writeToFile:resultFile
                           atomically:YES
                             encoding:NSUTF8StringEncoding
                                error:&err];
    NSLog(@"[ImagePickerDelegate] writeToFile ok=%d err=%@", ok, err);

    BOOL exists = [[NSFileManager defaultManager] fileExistsAtPath:resultFile];
    NSLog(@"[ImagePickerDelegate] result file exists immediately? %@", exists ? @"YES" : @"NO");
    
    NSDictionary *attrs = [[NSFileManager defaultManager] attributesOfItemAtPath:resultFile error:nil];
    NSLog(@"[ImagePickerDelegate] result file attrs: %@", attrs);


    // Dismiss picker
    UIViewController *root = UIApplication.sharedApplication.keyWindow.rootViewController;
    [root dismissViewControllerAnimated:YES completion:nil];
}

- (void)imagePickerControllerDidCancel:(UIImagePickerController *)picker
{
    NSLog(@"imagePickerControllerDidCancel fired");

    // Write an empty indicator so Python knows it was cancelled
    NSString *docs = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,
        NSUserDomainMask, YES).firstObject;

    NSString *ipcDir = [docs stringByAppendingPathComponent:@"gomapp_ipc"];
    [[NSFileManager defaultManager] createDirectoryAtPath:ipcDir
                              withIntermediateDirectories:YES
                                               attributes:nil
                                                    error:nil];

    NSString *resultFile = [ipcDir stringByAppendingPathComponent:@"picker_result.txt"];
    [@"__cancelled__" writeToFile:resultFile atomically:YES
                         encoding:NSUTF8StringEncoding error:nil];

    UIViewController *root = UIApplication.sharedApplication.keyWindow.rootViewController;
    [root dismissViewControllerAnimated:YES completion:nil];
}

@end
